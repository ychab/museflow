from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.domain.entities.user import User
from museflow.domain.enums import TasteProfiler
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.config.settings.openrouter import LLMSettings
from museflow.infrastructure.entrypoints.cli.commands.taste.build import build_logic

from tests.unit.factories.entities.taste import TasteProfileFactory


class TestTasteBuildLogic:
    """
    The purpose of this test is to check that the user is loaded correctly from DB.
    Otherwise, we trust use case integration tests and avoid duplication.
    """

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.build.BuildTasteProfileUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    @pytest.fixture(autouse=True)
    def mock_check_models(self) -> Iterable[mock.AsyncMock]:
        # The DI client targets the real OpenRouter catalog: the check itself is covered by the client tests on WireMock.
        with mock.patch.object(OpenRouterClient, "check_models", new_callable=mock.AsyncMock) as patched:
            yield patched

    async def test__nominal(
        self,
        user: User,
        mock_use_case: mock.Mock,
        mock_check_models: mock.AsyncMock,
    ) -> None:
        expected_profile = TasteProfileFactory.build(user_id=user.id)
        mock_use_case.build_profile.return_value = expected_profile

        profile = await build_logic(
            email=user.email,
            profiler=TasteProfiler.GEMINI,
            name="my-profile",
            resume=False,
            rated_only=False,
            track_limit=3000,
            batch_size=200,
            reflect_model="anthropic/claude-sonnet-4.5",
        )

        assert profile == expected_profile
        mock_check_models.assert_awaited_once()
        steps: dict[str, LLMSettings] = mock_check_models.call_args.args[0]
        assert list(steps) == ["profiler segment", "profiler merge", "profiler reflect"]
        assert steps["profiler reflect"].MODEL == "anthropic/claude-sonnet-4.5"
