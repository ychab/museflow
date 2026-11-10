from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_discover import DiscoverTasteUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import TrackSource
from museflow.domain.services.reconciler import Reconciler
from museflow.infrastructure.adapters.advisors.openrouter.client import OpenRouterAdvisorAdapter
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel
from museflow.infrastructure.adapters.database.models.track import Track as TrackModel

from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.track import TrackModelFactory
from tests.unit.factories.entities.track import TrackFactory


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
            config=DiscoverTasteConfigInput(prompt="lo-fi jazz and soul for focus", playlist_limit=2, dry_run=False),
        )

        assert result.playlist is not None
        assert result.playlist.provider_id == "5ta70oLZcXLReU7bEEXQXy"
        assert result.playlist.prompt == "lo-fi jazz and soul for focus"
        assert result.playlist.focus is None
        assert result.playlist.reasoning == result.strategy.reasoning
        assert result.strategy.strategy_label == "Progressive Horizons"
        assert result.strategy.suggested_playlist_name == "Sonic Expansion - Progressive Horizons"
        # The picks "1" and "2" are the first two candidates; the made-up id "99" is dropped.
        assert [(track.name, track.album_year) for track in result.tracks] == [
            ("Mi Pueblo", 1988),
            ("Mi Pueblo Natal", 2005),
        ]
        # The search pages hold 8 tracks of the artist, versions of 2 songs.
        assert [(r.attempt, r.artists, r.candidates, r.tracks_picked) for r in result.reports] == [(1, 1, 2, 2)]

        tracks_db = (
            (await async_session_db.execute(select(TrackModel).where(TrackModel.user_id == user.id))).scalars().all()
        )
        assert {track.name for track in tracks_db} == {"Mi Pueblo", "Mi Pueblo Natal"}
        assert {track.source for track in tracks_db} == {TrackSource.DISCOVERY}

        rows = (
            (await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id)))
            .scalars()
            .all()
        )
        assert sorted((row.operation, row.step) for row in rows) == [
            (LLMOperation.DISCOVER, "advisor_artists"),
            (LLMOperation.DISCOVER, "advisor_picks"),
        ]
        assert {(row.profile_id, row.playlist_id) for row in rows} == {(profile_db.id, result.playlist.id)}

    async def test__dry_run(
        self,
        async_session_db: AsyncSession,
        use_case: DiscoverTasteUseCase,
        user: User,
    ) -> None:
        profile_db = await TasteProfileModelFactory.create_async(user_id=user.id)

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=1, dry_run=True),
        )

        assert result.playlist is None
        assert len(result.tracks) == 1

        tracks_db = (await async_session_db.execute(select(TrackModel).where(TrackModel.user_id == user.id))).all()
        assert tracks_db == []
        rows = (
            (await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id)))
            .scalars()
            .all()
        )
        assert {(row.profile_id, row.playlist_id) for row in rows} == {(profile_db.id, None)}

    async def test__known_tracks__not_offered(self, use_case: DiscoverTasteUseCase, user: User) -> None:
        await TasteProfileModelFactory.create_async(user_id=user.id)
        known = TrackFactory.build(name="Mi Pueblo", artists=["Grupo Niche"])
        await TrackModelFactory.create_async(user_id=user.id, fingerprint=known.fingerprint)

        result = await use_case.create_suggestions_playlist(
            user=user,
            config=DiscoverTasteConfigInput(playlist_limit=1, dry_run=True),
        )

        # The only candidate left gets the id "1": the picks "2" and "99" point at nothing.
        assert [track.name for track in result.tracks] == ["Mi Pueblo Natal"]
        assert [(r.attempt, r.artists, r.candidates, r.tracks_picked) for r in result.reports] == [(1, 1, 1, 1)]
