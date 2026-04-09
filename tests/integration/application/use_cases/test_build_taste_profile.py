from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.use_cases.build_taste_profile import BuildTasteProfileUseCase
from museflow.domain.entities.user import User
from museflow.domain.types import TasteProfiler
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel
from museflow.infrastructure.adapters.profilers.gemini.client import GeminiTasteProfileAdapter

from tests.integration.factories.models.music import TrackModelFactory
from tests.unit.factories.inputs.taste import BuildTasteProfileConfigInputFactory


@pytest.mark.wiremock("gemini")
class TestGeminiBuildTasteProfileUseCase:
    @pytest.fixture
    def config(self) -> BuildTasteProfileConfigInput:
        return BuildTasteProfileConfigInputFactory.build(
            track_limit=100,
            batch_size=5,
            throttling_sleep_seconds=0.0,
        )

    @pytest.fixture
    def use_case(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        track_repository: TrackRepository,
        taste_profile_repository: TasteProfileRepository,
    ) -> BuildTasteProfileUseCase:
        return BuildTasteProfileUseCase(
            profiler=gemini_profiler,
            track_repository=track_repository,
            taste_profile_repository=taste_profile_repository,
        )

    async def test__nominal(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        async_session_db: AsyncSession,
    ) -> None:
        await TrackModelFactory.create_batch_async(size=7, user_id=user.id)

        profile = await use_case.build_profile(user=user, config=config)

        assert profile.tracks_count == 7
        assert profile.user_id == user.id
        assert profile.profiler == TasteProfiler.GEMINI
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

    async def test__upsert(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        async_session_db: AsyncSession,
    ) -> None:
        await TrackModelFactory.create_batch_async(size=3, user_id=user.id)

        await use_case.build_profile(user=user, config=config)
        await use_case.build_profile(user=user, config=config)

        stmt = select(func.count()).where(TasteProfileModel.user_id == user.id)
        count = (await async_session_db.execute(stmt)).scalar_one()
        assert count == 1
