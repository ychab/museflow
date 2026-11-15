from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.explore import ExploreArtistsConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.artists_explore import ExploreArtistsUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import PlaylistType
from museflow.domain.enums import TrackSource
from museflow.infrastructure.adapters.advisors.openrouter.client import OpenRouterAdvisorAdapter
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel
from museflow.infrastructure.adapters.database.models.track import Track as TrackModel

from tests.integration.factories.models.track import TrackModelFactory


@pytest.mark.wiremock("openrouter", "spotify")
class TestExploreArtistsUseCase:
    @pytest.fixture
    def use_case(
        self,
        uow: UnitOfWorkPort,
        spotify_library: ProviderLibraryPort,
        openrouter_advisor: OpenRouterAdvisorAdapter,
    ) -> ExploreArtistsUseCase:
        return ExploreArtistsUseCase(uow=uow, provider_library=spotify_library, advisor=openrouter_advisor)

    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        use_case: ExploreArtistsUseCase,
        user: User,
    ) -> None:
        """The favourite artist comes from the user's ratings, with no taste profile: its catalogue is searched."""
        await TrackModelFactory.create_async(
            user_id=user.id, name="Cali Pachanguero", artists=["Grupo Niche"], score=9
        )

        result = await use_case.create_playlist(
            user=user,
            # The search stub serves 2 pages per query, here one per release year range.
            config=ExploreArtistsConfigInput(catalogue_tracks_pages=2, playlist_limit=2),
        )

        assert result.playlist is not None
        assert result.playlist.type == PlaylistType.EXPLORE
        assert result.playlist.profile_id is None
        assert result.playlist.name.startswith("[MF] - Explore - ")
        # The picks "1" and "2" are the first two candidates; the made-up id "99" is dropped.
        assert [track.name for track in result.tracks] == ["Mi Pueblo", "Mi Pueblo Natal"]
        # The catalogue holds 8 tracks of the artist, versions of 2 songs.
        assert [(r.attempt, r.artists, r.candidates, r.tracks_picked) for r in result.reports] == [(1, 1, 2, 2)]

        tracks_db = (
            (await async_session_db.execute(select(TrackModel).where(TrackModel.source == TrackSource.DISCOVERY)))
            .scalars()
            .all()
        )
        assert {track.name for track in tracks_db} == {"Mi Pueblo", "Mi Pueblo Natal"}

        rows = (
            (await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id)))
            .scalars()
            .all()
        )
        assert [(row.operation, row.step, row.playlist_id) for row in rows] == [
            (LLMOperation.EXPLORE, "advisor_exploration_picks", result.playlist.id)
        ]

    async def test__dry_run(
        self,
        async_session_db: AsyncSession,
        use_case: ExploreArtistsUseCase,
        user: User,
    ) -> None:
        await TrackModelFactory.create_async(user_id=user.id, artists=["Grupo Niche"], played_count=3)

        result = await use_case.create_playlist(
            user=user,
            config=ExploreArtistsConfigInput(catalogue_tracks_pages=2, playlist_limit=1, dry_run=True),
        )

        assert result.playlist is None
        assert len(result.tracks) == 1
        tracks_db = (
            await async_session_db.execute(select(TrackModel).where(TrackModel.source == TrackSource.DISCOVERY))
        ).all()
        assert tracks_db == []
