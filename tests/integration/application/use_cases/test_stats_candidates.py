from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.stats_candidates import get_artist_candidates
from museflow.domain.entities.user import User
from museflow.domain.enums import SourceFilter

from tests.integration.factories.models.track import TrackModelFactory


class TestGetArtistCandidatesUseCase:
    async def test__nominal(self, uow: UnitOfWorkPort, user: User) -> None:
        # Hidden Gem: 1 track scored 9 — qualifies (total=1 ≤ 5, avg=9.0 ≥ 7.0)
        # Big Name: 6 tracks — excluded (total > 5)
        # Mediocre: 1 track scored 4 — excluded (avg < 7.0)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Hidden Gem"], score=9)
        await TrackModelFactory.create_batch_async(size=6, user_id=user.id, artists=["Big Name"], score=9)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Mediocre"], score=4)

        result = await get_artist_candidates(
            user_id=user.id, limit=20, source=SourceFilter.ALL, max_tracks=5, min_avg=7.0, uow=uow
        )

        assert len(result) == 1
        assert result[0].artist == "Hidden Gem"
        assert result[0].avg_score == 9.0
        assert result[0].rated_count == 1
        assert result[0].total_count == 1
