from collections.abc import Iterator
from unittest import mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_discover import DiscoverTasteUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import DiscoveryPlayedMode
from museflow.domain.enums import LLMOperation
from museflow.domain.services.reconciler import Reconciler
from museflow.infrastructure.adapters.advisors.openrouter.client import OpenRouterAdvisorAdapter
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel

from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.track import TrackModelFactory


@pytest.mark.wiremock("openrouter", "spotify")
class TestDiscoverTasteUseCase:
    @pytest.fixture
    def use_case(
        self,
        uow: UnitOfWorkPort,
        spotify_library: ProviderLibraryPort,
        openrouter_advisor: OpenRouterAdvisorAdapter,
        reconciler: Reconciler,
    ) -> DiscoverTasteUseCase:
        return DiscoverTasteUseCase(
            uow=uow,
            provider_library=spotify_library,
            advisor=openrouter_advisor,
            reconciler=reconciler,
        )

    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        use_case: DiscoverTasteUseCase,
        user: User,
    ) -> None:
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id)

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                prompt="lo-fi jazz and soul for focus",
                playlist_limit=1,
                advisor_limit=5,
                dry_run=False,
            ),
        )

        assert result.playlist is not None
        assert result.playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
        assert result.playlist.prompt == "lo-fi jazz and soul for focus"
        assert result.playlist.focus is None
        assert len(result.playlist.tracks) == len(result.tracks)
        assert result.strategy.strategy_label == "Progressive Horizons"
        assert result.strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"
        assert len(result.tracks) >= 1

        row = (
            await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id))
        ).scalar_one()
        assert (row.operation, row.step) == (LLMOperation.DISCOVER, "advisor")
        assert row.profile_id == profile_db.id
        assert row.playlist_id == result.playlist.id

    async def test__dry_run(
        self,
        async_session_db: AsyncSession,
        use_case: DiscoverTasteUseCase,
        user: User,
    ) -> None:
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id)

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_limit=1,
                advisor_limit=5,
                dry_run=True,
            ),
        )

        assert result.playlist is None
        assert result.strategy.strategy_label == "Progressive Horizons"
        assert result.strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"

        row = (
            await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id))
        ).scalar_one()
        assert row.profile_id == profile_db.id
        assert row.playlist_id is None

    @pytest.fixture
    def spy_get_discovery_strategy(self, openrouter_advisor: OpenRouterAdvisorAdapter) -> Iterator[mock.AsyncMock]:
        with mock.patch.object(
            openrouter_advisor,
            "get_discovery_strategy",
            wraps=openrouter_advisor.get_discovery_strategy,
        ) as spy:
            yield spy

    @pytest.mark.parametrize(
        ("played_mode", "expected_played_tracks", "expected_played_artists"),
        [
            pytest.param(
                DiscoveryPlayedMode.TRACKS,
                ["Most Played", "Second Hit", "Played Once"],
                None,
                id="tracks",
            ),
            pytest.param(
                DiscoveryPlayedMode.ARTISTS,
                None,
                ["The Fictional Band", "Another Band"],
                id="artists",
            ),
        ],
    )
    async def test__played_tracks(
        self,
        use_case: DiscoverTasteUseCase,
        user: User,
        spy_get_discovery_strategy: mock.AsyncMock,
        played_mode: DiscoveryPlayedMode,
        expected_played_tracks: list[str] | None,
        expected_played_artists: list[str] | None,
    ) -> None:
        """Only the unrated tracks played at least once are sent, most played first, as tracks or artists."""
        await TasteProfileModelFactory.create_async(user_id=user.id)
        await TrackModelFactory.create_async(
            user_id=user.id, name="Played Once", artists=["The Fictional Band"], score=None, played_count=1
        )
        await TrackModelFactory.create_async(
            user_id=user.id, name="Most Played", artists=["The Fictional Band"], score=None, played_count=3
        )
        await TrackModelFactory.create_async(
            user_id=user.id, name="Second Hit", artists=["Another Band"], score=None, played_count=2
        )
        await TrackModelFactory.create_async(user_id=user.id, name="Rated", score=5, played_count=5)
        await TrackModelFactory.create_async(user_id=user.id, name="Never Played", score=None)

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_limit=1,
                advisor_limit=5,
                played_mode=played_mode,
                played_tracks_limit=10,
                dry_run=True,
            ),
        )

        kwargs = spy_get_discovery_strategy.call_args_list[0].kwargs
        played_tracks = kwargs["played_tracks"]
        assert ([t.name for t in played_tracks] if played_tracks else None) == expected_played_tracks
        assert kwargs["played_artists"] == expected_played_artists
