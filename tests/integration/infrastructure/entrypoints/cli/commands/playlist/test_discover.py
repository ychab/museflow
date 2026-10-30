from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.use_cases.taste_discover import DiscoverTasteResult
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicAdvisor
from museflow.domain.enums import MusicProvider
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy
from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.config.settings.openrouter import LLMSettings
from museflow.infrastructure.entrypoints.cli.commands.playlist.discover import discover_logic

from tests.unit.factories.entities.playlist import PlaylistFactory


class TestDiscoverLogic:
    """
    The purpose of this test is to check that the user and the auth token are loaded correctly.
    Otherwise, we trust use case integration tests and avoid duplication.
    """

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.playlist.discover.DiscoverTasteUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    @pytest.fixture(autouse=True)
    def mock_check_models(self) -> Iterable[mock.AsyncMock]:
        # The DI client targets the real OpenRouter catalog: the check itself is covered by the client tests on WireMock.
        with mock.patch.object(OpenRouterClient, "check_models", new_callable=mock.AsyncMock) as patched:
            yield patched

    @pytest.mark.parametrize("advisor", list(MusicAdvisor))
    async def test__discover__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        advisor: MusicAdvisor,
        discovery_taste_strategy: DiscoveryTasteStrategy,
        mock_use_case: mock.Mock,
        mock_check_models: mock.AsyncMock,
    ) -> None:
        expected_result = DiscoverTasteResult(
            playlist=PlaylistFactory.build(user_id=user.id),
            strategy=discovery_taste_strategy,
            reports=[],
            tracks=[],
        )
        mock_use_case.create_suggestions_playlist.return_value = expected_result

        result = await discover_logic(
            email=user.email,
            advisor=advisor,
            provider=MusicProvider.SPOTIFY,
            config=DiscoverTasteConfigInput(),
            model="openai/gpt-5-mini",
        )

        assert result == expected_result
        mock_check_models.assert_awaited_once()
        steps: dict[str, LLMSettings] = mock_check_models.call_args.args[0]
        assert steps["advisor"].MODEL == "openai/gpt-5-mini"
