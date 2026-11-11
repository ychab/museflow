from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.enums import RankingSortBy
from museflow.domain.enums import SourceFilter
from museflow.infrastructure.entrypoints.cli.commands.stats.tags import stats_tags_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestStatsTagsLogic:
    async def test__nominal(self, user: User) -> None:
        await TrackModelFactory.create_async(user_id=user.id, moods=["chill", "dreamy"], score=8, played_count=2)
        await TrackModelFactory.create_async(user_id=user.id, moods=["chill"], score=6, played_count=1)
        await TrackModelFactory.create_async(user_id=user.id, moods=[], score=None)

        result = await stats_tags_logic(
            email=user.email,
            by=EnrichField.MOOD,
            tier=None,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=RankingSortBy.TRACK_COUNT,
            limit=20,
        )

        assert [(r.stats.tag, r.stats.track_count, r.stats.plays_count) for r in result.rankings] == [
            ("chill", 2, 3),
            ("dreamy", 1, 2),
        ]
        assert result.unenriched_count == 1
