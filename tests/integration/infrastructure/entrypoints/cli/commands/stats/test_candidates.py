from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.stats import SourceFilter
from museflow.infrastructure.entrypoints.cli.commands.stats.candidates import candidates_logic

from tests.integration.factories.models.music import TrackModelFactory


class TestStatsCandidatesLogic:
    async def test__nominal(self, user: User) -> None:
        # Hidden Gem: 1 track scored 9 — qualifies (total=1 ≤ 5, avg=9.0 ≥ 7.0)
        # Big Name: 6 tracks — excluded (total > 5)
        # Mediocre: 1 track scored 4 — excluded (avg < 7.0)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Hidden Gem"], score=9)
        await TrackModelFactory.create_batch_async(size=6, user_id=user.id, artists=["Big Name"], score=9)
        await TrackModelFactory.create_async(user_id=user.id, artists=["Mediocre"], score=4)

        result = await candidates_logic(
            email=user.email,
            limit=20,
            source=SourceFilter.ALL,
            max_tracks=5,
            min_avg=7.0,
        )

        assert len(result) == 1
        assert result[0].artist == "Hidden Gem"
        assert result[0].avg_score == 9.0
        assert result[0].rated_count == 1
        assert result[0].total_count == 1
