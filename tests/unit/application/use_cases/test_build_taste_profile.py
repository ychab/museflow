import json
from typing import Any
from unittest import mock

import pytest
from pytest_httpx import HTTPXMock

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.use_cases.build_taste_profile import BuildTasteProfileUseCase
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.user import User
from museflow.domain.exceptions import TasteProfileNoSeedException
from museflow.infrastructure.adapters.profilers.gemini.client import GeminiTasteProfileAdapter

from tests.integration.factories.models.taste import TasteProfileDataFactory
from tests.unit.factories.entities.music import TrackFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.inputs.taste import BuildTasteProfileConfigInputFactory


class TestBuildTasteProfileUseCase:
    @pytest.fixture
    def profile_data(self) -> TasteProfileData:
        return TasteProfileDataFactory.build(personality_archetype=None, life_phase_insights=[])

    @pytest.fixture
    def gemini_response(self, profile_data: TasteProfileData) -> dict[str, Any]:
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(profile_data)}],
                        "role": "model",
                    }
                }
            ]
        }

    @pytest.fixture
    def config(self) -> BuildTasteProfileConfigInput:
        return BuildTasteProfileConfigInputFactory.build(track_limit=10, batch_size=3)

    @pytest.fixture
    def use_case(
        self,
        gemini_profiler: GeminiTasteProfileAdapter,
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> BuildTasteProfileUseCase:
        return BuildTasteProfileUseCase(
            profiler=gemini_profiler,
            track_repository=mock_track_repository,
            taste_profile_repository=mock_taste_profile_repository,
        )

    async def test__nominal__multiple_batches(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
        profile_data: TasteProfileData,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        # 7 tracks → 3 batches (3 / 3 / 1)
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=7, user_id=user.id)

        # 3 build_profile_segment + 2 merge_profiles + 1 reflect_on_profile
        for _ in range(6):
            httpx_mock.add_response(
                url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
                method="POST",
                json=gemini_response,
            )

        expected_profile = TasteProfileFactory.build(user_id=user.id)
        mock_taste_profile_repository.upsert.return_value = expected_profile

        profile = await use_case.build_profile(user=user, config=config)

        assert profile is expected_profile
        mock_taste_profile_repository.upsert.assert_called_once()
        assert mock_taste_profile_repository.upsert.call_args.args[0].profile == profile_data

    async def test__nominal__single_batch(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
        profile_data: TasteProfileData,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        # 2 tracks → 1 batch → 1 build_profile_segment + 1 reflect_on_profile (no merge)
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=2, user_id=user.id)

        for _ in range(2):
            httpx_mock.add_response(
                url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
                method="POST",
                json=gemini_response,
            )

        mock_taste_profile_repository.upsert.return_value = TasteProfileFactory.build(user_id=user.id)

        profile = await use_case.build_profile(user=user, config=config)

        assert profile is not None
        assert profile.user_id == user.id
        assert mock_taste_profile_repository.upsert.call_args.args[0].profile == profile_data

    async def test__no_seed(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        with pytest.raises(TasteProfileNoSeedException):
            await use_case.build_profile(user=user, config=config)
