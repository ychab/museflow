from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.stats_tags import get_top_tags
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.enums import GenreTier
from museflow.domain.enums import RankingSortBy
from museflow.domain.enums import SourceFilter

from tests.integration.factories.models.track import TrackModelFactory


class TestGetTopTagsUseCase:
    async def test__nominal(self, uow: UnitOfWorkPort, user: User) -> None:
        # Library mean (8 + 6 + 4 + 10) / 4 = 7, over every track, the untagged one included.
        # rock: 2 tracks at 8 and 6 → quality (5*7 + 14) / 7 = 7.0; jazz: 1 track at 4 → (5*7 + 4) / 6 = 6.5
        await TrackModelFactory.create_async(user_id=user.id, genres=["rock", "post-rock"], score=8)
        await TrackModelFactory.create_async(user_id=user.id, genres=["rock", "indie-rock"], score=6)
        await TrackModelFactory.create_async(user_id=user.id, genres=["jazz", "bebop"], score=4)
        await TrackModelFactory.create_async(user_id=user.id, genres=[], score=10)

        result = await get_top_tags(
            user_id=user.id,
            field=EnrichField.GENRE,
            tier=GenreTier.MACRO,
            source=SourceFilter.ALL,
            score_min=None,
            score_max=None,
            confidence=5,
            sort=RankingSortBy.QUALITY,
            limit=20,
            uow=uow,
        )

        assert [r.stats.tag for r in result.rankings] == ["rock", "jazz"]
        assert result.rankings[0].quality_score == 7.0
        assert result.rankings[1].quality_score == 6.5
        assert result.unenriched_count == 1
