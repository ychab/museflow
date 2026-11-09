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

    async def test__top_listening(
        self,
        use_case: DiscoverTasteUseCase,
        user: User,
        spy_get_discovery_strategy: mock.AsyncMock,
    ) -> None:
        """The most played tracks besides the liked ones, and the artists owned the most, reach the advisor."""
        await TasteProfileModelFactory.create_async(user_id=user.id)
        await TrackModelFactory.create_async(
            user_id=user.id, name="Liked", artists=["The Fictional Band"], score=9, played_count=9
        )
        await TrackModelFactory.create_async(
            user_id=user.id, name="Most Played", artists=["The Fictional Band"], score=None, played_count=3
        )
        await TrackModelFactory.create_async(
            user_id=user.id, name="Rated Average", artists=["Another Band"], score=5, played_count=2
        )
        await TrackModelFactory.create_async(
            user_id=user.id, name="Never Played", artists=["Another Band"], score=None
        )
        await TrackModelFactory.create_async(user_id=user.id, name="Lonely", artists=["A Third Band"], score=None)

        await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(
                playlist_limit=1,
                advisor_limit=5,
                top_played_tracks_limit=10,
                top_artists_limit=2,
                dry_run=True,
            ),
        )

        kwargs = spy_get_discovery_strategy.call_args_list[0].kwargs
        assert [t.name for t in kwargs["top_played_tracks"]] == ["Most Played", "Rated Average"]
        assert kwargs["top_artists"] == {"Another Band": 2, "The Fictional Band": 2}
