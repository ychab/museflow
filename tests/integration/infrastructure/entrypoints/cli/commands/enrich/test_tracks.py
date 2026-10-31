from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.use_cases.tracks_enrich import EnrichTracksReport
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.config.settings.openrouter import LLMSettings
from museflow.infrastructure.entrypoints.cli.commands.enrich.tracks import enrich_logic


class TestEnrichTracksLogic:
    """Tests only the CLI logic's own behavior: user lookup + delegation to the use case."""

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.enrich.tracks.EnrichTracksUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value.enrich.return_value = EnrichTracksReport(enriched_count=1, error_count=0)
            yield patched.return_value

    @pytest.fixture(autouse=True)
    def mock_check_models(self) -> Iterable[mock.AsyncMock]:
        # The DI client targets the real OpenRouter catalog: the check itself is covered by the client tests on WireMock.
        with mock.patch.object(OpenRouterClient, "check_models", new_callable=mock.AsyncMock) as patched:
            yield patched

    async def test__nominal(self, user: User, mock_use_case: mock.Mock, mock_check_models: mock.AsyncMock) -> None:
        result = await enrich_logic(email=user.email, model="openai/gpt-5-mini")

        assert result.enriched_count == 1
        called_user = mock_use_case.enrich.call_args.kwargs["user"]
        assert called_user.id == user.id
        mock_check_models.assert_awaited_once()
        steps: dict[str, LLMSettings] = mock_check_models.call_args.args[0]
        assert steps["enricher"].MODEL == "openai/gpt-5-mini"

    async def test__user_not_found(self, mock_use_case: mock.Mock) -> None:
        with pytest.raises(UserNotFound):
            await enrich_logic(email="nobody@example.com")
