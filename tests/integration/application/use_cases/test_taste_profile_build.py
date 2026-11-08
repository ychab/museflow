from datetime import UTC
from datetime import datetime

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.taste_profile_build import BuildTasteProfileUseCase
from museflow.domain.entities.user import User
from museflow.domain.enums import LLMOperation
from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel
from museflow.infrastructure.adapters.profilers.openrouter.client import OpenRouterTasteProfileAdapter

from tests.integration.factories.models.track import TrackModelFactory
from tests.integration.factories.models.track import TrackPlayModelFactory
from tests.unit.factories.inputs.taste import BuildTasteProfileConfigInputFactory


@pytest.mark.wiremock("openrouter")
class TestBuildTasteProfileUseCase:
    @pytest.fixture
    def config(self) -> BuildTasteProfileConfigInput:
        return BuildTasteProfileConfigInputFactory.build(
            track_limit=100,
            batch_size=2,
            throttling_sleep_seconds=0.0,
        )

    @pytest.fixture
    def use_case(
        self,
        uow: UnitOfWorkPort,
        openrouter_profiler: OpenRouterTasteProfileAdapter,
    ) -> BuildTasteProfileUseCase:
        return BuildTasteProfileUseCase(
            profiler=openrouter_profiler,
            uow=uow,
        )

    async def test__nominal(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        async_session_db: AsyncSession,
    ) -> None:
        # 6 plays in 2 periods of 3: the replayed track seeds both periods, the never-played one none.
        replayed, early, late, _ = [await TrackModelFactory.create_async(user_id=user.id) for _ in range(4)]
        for track_db, day in [(replayed, 1), (replayed, 2), (early, 3)]:
            await TrackPlayModelFactory.create_async(
                track_id=track_db.id, played_at=datetime(2020, 1, day, tzinfo=UTC)
            )
        for track_db, day in [(replayed, 1), (replayed, 2), (late, 3)]:
            await TrackPlayModelFactory.create_async(
                track_id=track_db.id, played_at=datetime(2022, 1, day, tzinfo=UTC)
            )

        profile = await use_case.build_profile(user=user, config=config)

        assert profile.tracks_count == 4  # 2 seeds a period, the replayed track in both
        assert profile.user_id == user.id
        assert profile.logic_version == "v2.2"
        assert profile.profiler_metadata["gateway"] == "openrouter"
        assert profile.profile["personality_archetype"] == "The Introspective Wanderer"
        assert profile.profile["life_phase_insights"] == [
            "Transition from high-energy rock to ambient introspection during 2022"
        ]
        assert profile.profile["musical_identity_summary"] is not None
        assert profile.profile["behavioral_traits"] == {
            "openness": 0.8,
            "adventurousness": 0.7,
            "nostalgia_bias": 0.4,
            "rhythmic_dependency": 0.6,
        }
        assert profile.profile["discovery_style"] == "The Deep Diver"

        stmt = select(func.count()).where(TasteProfileModel.user_id == user.id)
        count = (await async_session_db.execute(stmt)).scalar_one()
        assert count == 1

        rows = (
            await async_session_db.execute(select(LLMUsageModel).where(LLMUsageModel.user_id == user.id))
        ).scalars()
        assert {(row.operation, row.step, row.profile_id, row.calls) for row in rows} == {
            (LLMOperation.TASTE_BUILD, "profiler segment", profile.id, 2),
            (LLMOperation.TASTE_BUILD, "profiler merge", profile.id, 1),
            (LLMOperation.TASTE_BUILD, "profiler reflect", profile.id, 1),
        }

    async def test__upsert(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        async_session_db: AsyncSession,
    ) -> None:
        await TrackModelFactory.create_batch_async(size=3, user_id=user.id, played_count=1)

        await use_case.build_profile(user=user, config=config)
        await use_case.build_profile(user=user, config=config)

        stmt = select(func.count()).where(TasteProfileModel.user_id == user.id)
        count = (await async_session_db.execute(stmt)).scalar_one()
        assert count == 1
