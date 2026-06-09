import json
from datetime import UTC
from datetime import datetime
from typing import Any
from unittest import mock

import pytest
from pytest_httpx import HTTPXMock

from museflow.application.inputs.taste import BuildTasteProfileConfigInput
from museflow.application.use_cases.taste_profile_build import BuildTasteProfileUseCase
from museflow.domain.entities.music import Track
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.user import User
from museflow.domain.exceptions import TasteProfileBuildException
from museflow.domain.exceptions import TasteProfileBuildPausedException
from museflow.domain.exceptions import TasteProfileNoSeedException
from museflow.domain.exceptions import TasteProfilerRateLimitExceeded
from museflow.infrastructure.adapters.profilers.gemini.client import GeminiTasteProfileAdapter

from tests.integration.factories.models.taste import TasteProfileDataFactory
from tests.unit.factories.entities.music import TrackFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.inputs.taste import BuildTasteProfileConfigInputFactory


class TestBuildTasteProfileUseCase:
    @pytest.fixture
    def profile_data(self) -> TasteProfileData:
        return TasteProfileDataFactory.build(
            personality_archetype=None,
            life_phase_insights=[],
            # Use pre-normalized keys and valid weights so normalization is a no-op
            core_identity={"indie rock": 0.8, "electronic": 0.4},
            current_vibe={"hip hop": 0.6},
        )

    @pytest.fixture
    def gemini_response(self, profile_data: TasteProfileData) -> dict[str, Any]:
        serializable = {
            **profile_data,
            "core_identity": [{"key": k, "value": v} for k, v in profile_data["core_identity"].items()],
            "current_vibe": [{"key": k, "value": v} for k, v in profile_data["current_vibe"].items()],
        }

        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(serializable)}],
                        "role": "model",
                    }
                }
            ]
        }

    @pytest.fixture
    def config(self) -> BuildTasteProfileConfigInput:
        return BuildTasteProfileConfigInputFactory.build(
            track_limit=10,
            batch_size=3,
            throttling_sleep_seconds=0.0,
        )

    @pytest.fixture
    def tracks(self, request: pytest.FixtureRequest, user: User) -> list[Track]:
        size: int = request.param
        return [
            TrackFactory.build(
                user_id=user.id,
                played_at_last=datetime(2020, 1, i + 1, tzinfo=UTC),
                played_at_first=datetime(2019, 1, i + 1, tzinfo=UTC),
            )
            for i in range(size)
        ]

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

    @pytest.mark.parametrize("tracks", [7], indirect=True)
    async def test__nominal__multiple_batches(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        tracks: list[Track],
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
        profile_data: TasteProfileData,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        # 7 tracks → 3 batches (3 / 3 / 1)
        mock_track_repository.get_list.return_value = tracks

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

    @pytest.mark.parametrize("tracks", [2], indirect=True)
    async def test__nominal__single_batch(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        tracks: list[Track],
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
        profile_data: TasteProfileData,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        # 2 tracks → 1 batch → 1 build_profile_segment + 1 reflect_on_profile (no merge)
        mock_track_repository.get_list.return_value = tracks

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

    @pytest.mark.parametrize("tracks", [7], indirect=True)
    async def test__throttling(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        tracks: list[Track],
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
        profile_data: TasteProfileData,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        # 7 tracks → 3 batches (3 / 3 / 1) — sleep called twice (between batch 1→2 and 2→3, not after last)
        config = BuildTasteProfileConfigInputFactory.build(
            track_limit=10,
            batch_size=3,
            throttling_sleep_seconds=1.0,
        )
        mock_track_repository.get_list.return_value = tracks

        for _ in range(6):
            httpx_mock.add_response(
                url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
                method="POST",
                json=gemini_response,
            )

        mock_taste_profile_repository.upsert.return_value = TasteProfileFactory.build(user_id=user.id)

        with mock.patch("museflow.application.use_cases.taste_profile_build.asyncio.sleep") as mock_sleep:
            await use_case.build_profile(user=user, config=config)

        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1.0)

    @pytest.mark.parametrize("tracks", [7], indirect=True)
    async def test__no_throttling(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        config: BuildTasteProfileConfigInput,
        tracks: list[Track],
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
        profile_data: TasteProfileData,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        # throttling_sleep_seconds=0.0 (default from factory) — sleep never called
        mock_track_repository.get_list.return_value = tracks

        for _ in range(6):
            httpx_mock.add_response(
                url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
                method="POST",
                json=gemini_response,
            )

        mock_taste_profile_repository.upsert.return_value = TasteProfileFactory.build(user_id=user.id)

        with mock.patch("museflow.application.use_cases.taste_profile_build.asyncio.sleep") as mock_sleep:
            await use_case.build_profile(user=user, config=config)

        mock_sleep.assert_not_called()

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

    @pytest.mark.parametrize("tracks", [7], indirect=True)
    async def test__resume__checkpoint_found(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        tracks: list[Track],
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
        profile_data: TasteProfileData,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        # Checkpoint at batch 1 — only batches 2 and 3 are processed (2 segment + 2 merge + 1 reflect = 5 calls)
        config = BuildTasteProfileConfigInputFactory.build(track_limit=10, batch_size=3, resume=True)
        mock_track_repository.get_list.return_value = tracks
        mock_taste_profile_repository.get_checkpoint.return_value = (profile_data, 1)
        mock_taste_profile_repository.upsert.return_value = TasteProfileFactory.build(user_id=user.id)

        for _ in range(5):
            httpx_mock.add_response(
                url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
                method="POST",
                json=gemini_response,
            )

        await use_case.build_profile(user=user, config=config)

        mock_taste_profile_repository.get_checkpoint.assert_called_once_with(user.id, config.name)
        assert mock_taste_profile_repository.save_checkpoint.call_count == 2

    @pytest.mark.parametrize("tracks", [7], indirect=True)
    async def test__resume__no_checkpoint(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        tracks: list[Track],
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
        profile_data: TasteProfileData,
        gemini_response: dict[str, Any],
        httpx_mock: HTTPXMock,
    ) -> None:
        config = BuildTasteProfileConfigInputFactory.build(track_limit=10, batch_size=3, resume=True)
        mock_track_repository.get_list.return_value = tracks
        mock_taste_profile_repository.get_checkpoint.return_value = None
        mock_taste_profile_repository.upsert.return_value = TasteProfileFactory.build(user_id=user.id)

        for _ in range(6):
            httpx_mock.add_response(
                url=f"{gemini_profiler.base_url}models/gemini-2.5-flash:generateContent",
                method="POST",
                json=gemini_response,
            )

        await use_case.build_profile(user=user, config=config)

        mock_taste_profile_repository.get_checkpoint.assert_called_once_with(user.id, config.name)

    @pytest.mark.parametrize("tracks", [7], indirect=True)
    async def test__batch_fail__pauses__rate_limit_exceeded(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        tracks: list[Track],
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
    ) -> None:
        # Batch 1 raises TasteProfilerRateLimitExceeded — build pauses immediately, no checkpoint saved
        config = BuildTasteProfileConfigInputFactory.build(track_limit=10, batch_size=3)
        mock_track_repository.get_list.return_value = tracks

        with mock.patch.object(
            gemini_profiler,
            "build_profile_segment",
            new_callable=mock.AsyncMock,
            side_effect=TasteProfilerRateLimitExceeded("rate limit"),
        ):
            with pytest.raises(TasteProfileBuildPausedException) as exc_info:
                await use_case.build_profile(user=user, config=config)

        assert exc_info.value.batch_index == 1
        assert exc_info.value.total_batches == 3
        assert exc_info.value.reason == "rate limit"
        mock_taste_profile_repository.save_checkpoint.assert_not_called()
        mock_taste_profile_repository.upsert.assert_not_called()

    @pytest.mark.parametrize("tracks", [7], indirect=True)
    async def test__batch_fail__pauses__build_exception(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        tracks: list[Track],
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
    ) -> None:
        # Batch 1 raises TasteProfileBuildException — build pauses immediately, no checkpoint saved
        config = BuildTasteProfileConfigInputFactory.build(track_limit=10, batch_size=3)
        mock_track_repository.get_list.return_value = tracks

        with mock.patch.object(
            gemini_profiler,
            "build_profile_segment",
            new_callable=mock.AsyncMock,
            side_effect=TasteProfileBuildException("bad response"),
        ):
            with pytest.raises(TasteProfileBuildPausedException) as exc_info:
                await use_case.build_profile(user=user, config=config)

        assert exc_info.value.batch_index == 1
        assert exc_info.value.total_batches == 3
        assert exc_info.value.reason == "bad response"
        mock_taste_profile_repository.save_checkpoint.assert_not_called()
        mock_taste_profile_repository.upsert.assert_not_called()

    @pytest.mark.parametrize("tracks", [7], indirect=True)
    async def test__batch_fail__pauses__checkpoint_preserved(
        self,
        user: User,
        use_case: BuildTasteProfileUseCase,
        tracks: list[Track],
        mock_track_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
        gemini_profiler: GeminiTasteProfileAdapter,
        profile_data: TasteProfileData,
    ) -> None:
        # Batch 1 succeeds (checkpoint saved), batch 2 fails — pauses at 2/3, upsert never called
        config = BuildTasteProfileConfigInputFactory.build(track_limit=10, batch_size=3)
        mock_track_repository.get_list.return_value = tracks

        with mock.patch.object(
            gemini_profiler,
            "build_profile_segment",
            new_callable=mock.AsyncMock,
            side_effect=[profile_data, TasteProfilerRateLimitExceeded("rate limit")],
        ):
            with pytest.raises(TasteProfileBuildPausedException) as exc_info:
                await use_case.build_profile(user=user, config=config)

        assert exc_info.value.batch_index == 2
        assert exc_info.value.total_batches == 3
        assert exc_info.value.reason == "rate limit"
        mock_taste_profile_repository.save_checkpoint.assert_called_once()
        mock_taste_profile_repository.upsert.assert_not_called()
