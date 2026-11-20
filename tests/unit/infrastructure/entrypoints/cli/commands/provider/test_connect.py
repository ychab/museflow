from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderExchangeCodeError
from museflow.domain.exceptions import ProviderOAuthAuthorizationError
from museflow.domain.exceptions import ProviderOAuthStateInvalidError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.provider.connect import ConnectStart
from museflow.infrastructure.entrypoints.cli.commands.provider.connect import provider_connect_complete_logic
from museflow.infrastructure.entrypoints.cli.commands.provider.connect import provider_connect_start_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.auth import OAuthProviderStateFactory
from tests.unit.factories.entities.user import UserFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.provider.connect"
REDIRECT_URL: Final[str] = "http://127.0.0.1:65535/cli/callback?code=abc&state=xyz"


@pytest.fixture
def connect_start() -> ConnectStart:
    return ConnectStart(
        user=UserFactory.build(),
        provider=MusicProvider.SPOTIFY,
        authorization_url="http://example.com",
    )


@pytest.fixture
def mock_provider_connect_start_logic(connect_start: ConnectStart) -> Iterable[mock.AsyncMock]:
    with mock.patch(
        f"{TARGET_PATH}.provider_connect_start_logic",
        new_callable=mock.AsyncMock,
        return_value=connect_start,
    ) as patched:
        yield patched


@pytest.fixture
def mock_provider_connect_complete_logic() -> Iterable[mock.AsyncMock]:
    with mock.patch(f"{TARGET_PATH}.provider_connect_complete_logic", new_callable=mock.AsyncMock) as patched:
        yield patched


@pytest.fixture
def mock_typer_launch() -> Iterable[mock.Mock]:
    with mock.patch(f"{TARGET_PATH}.typer.launch") as patched:
        yield patched


@pytest.mark.usefixtures(
    "mock_provider_connect_start_logic",
    "mock_provider_connect_complete_logic",
    "mock_typer_launch",
)
class TestProviderConnectParserCommand:
    def test__nominal(
        self,
        mock_provider_connect_start_logic: mock.AsyncMock,
        mock_provider_connect_complete_logic: mock.AsyncMock,
        connect_start: ConnectStart,
        runner: CliRunner,
    ) -> None:
        result = runner.invoke(
            app,
            ["provider", "connect", "--email", "test@example.com", "--provider", "spotify"],
            input=f"{REDIRECT_URL}\n",
        )
        assert result.exit_code == 0
        mock_provider_connect_start_logic.assert_awaited_once_with("test@example.com", MusicProvider.SPOTIFY)
        mock_provider_connect_complete_logic.assert_awaited_once_with(connect_start, REDIRECT_URL)

    def test__provider__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com", "--provider", "foo"])
        assert result.exit_code != 0
        assert "Invalid value for '--provider'" in clean_typer_text(result.output)

    @pytest.mark.parametrize(
        ("email", "expected_msg"),
        [
            pytest.param(
                "testtest.com",
                "An email address must have an @-sign",
                id="missing_@",
            ),
            pytest.param(
                "test@test",
                "The part after the @-sign is not valid. It should have a period",
                id="missing_dot",
            ),
        ],
    )
    def test__email__invalid(
        self,
        runner: CliRunner,
        email: str,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["provider", "connect", "--email", email],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output


@pytest.mark.usefixtures(
    "mock_provider_connect_start_logic",
    "mock_provider_connect_complete_logic",
    "mock_typer_launch",
)
class TestProviderConnectCommand:
    def test__nominal(
        self,
        mock_typer_launch: mock.Mock,
        connect_start: ConnectStart,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"], input=f"{REDIRECT_URL}\n")
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert f"Opening browser for authentication: {connect_start.authorization_url}" in output
        assert "the browser lands on http://127.0.0.1:65535/cli/callback, which does not load" in output
        assert "Authentication successful!" in output
        mock_typer_launch.assert_called_once_with(connect_start.authorization_url)

    def test__user_not_found(
        self,
        mock_provider_connect_start_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_provider_connect_start_logic.side_effect = UserNotFoundError()

        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    @pytest.mark.parametrize(
        ("error", "expected_msg"),
        [
            pytest.param(
                ProviderOAuthStateInvalidError(),
                "The URL holds an unknown or expired state: run the command again.",
                id="state_invalid",
            ),
            pytest.param(
                ProviderOAuthAuthorizationError("access_denied"),
                "The provider refused the authorisation: access_denied",
                id="authorization_refused",
            ),
            pytest.param(
                ProviderExchangeCodeError(),
                "Unable to exchange the authorisation code with the provider",
                id="exchange_failed",
            ),
        ],
    )
    def test__oauth_error(
        self,
        mock_provider_connect_complete_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        error: Exception,
        expected_msg: str,
    ) -> None:
        mock_provider_connect_complete_logic.side_effect = error

        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"], input=f"{REDIRECT_URL}\n")
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert expected_msg in output

    def test__exception(
        self,
        mock_provider_connect_start_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_provider_connect_start_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures("mock_wiring")
class TestProviderConnectLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__start__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await provider_connect_start_logic("test@example.com", MusicProvider.SPOTIFY)

    @pytest.mark.parametrize(
        "redirect_url",
        [
            pytest.param("https://accounts.spotify.com/authorize?client_id=abc&state=xyz", id="authorization_url"),
            pytest.param("http://127.0.0.1:9999/cli/callback?code=abc&state=xyz", id="other_port"),
            pytest.param("abc", id="not_an_url"),
        ],
    )
    async def test__complete__not_redirect_url(
        self,
        mock_auth_state_repository: mock.AsyncMock,
        connect_start: ConnectStart,
        redirect_url: str,
    ) -> None:
        with pytest.raises(
            ValueError, match="Not the URL of the redirect: it starts with http://127.0.0.1:65535/cli/callback"
        ):
            await provider_connect_complete_logic(connect_start, redirect_url)

        # The state is left to its flow: a wrong paste doesn't spend it.
        mock_auth_state_repository.consume.assert_not_awaited()

    async def test__complete__state__other_user(
        self,
        mock_auth_state_repository: mock.AsyncMock,
        mock_provider_oauth: mock.AsyncMock,
        connect_start: ConnectStart,
        auth_state: OAuthProviderState,
    ) -> None:
        # The state of another flow, still valid: only the flow of this command may finish here.
        mock_auth_state_repository.consume.return_value = auth_state

        with pytest.raises(ProviderOAuthStateInvalidError):
            await provider_connect_complete_logic(
                connect_start,
                f"http://127.0.0.1:65535/cli/callback?code=abc&state={auth_state.state}",
            )

        mock_provider_oauth.exchange_code_for_token.assert_not_awaited()

    @pytest.mark.parametrize(
        ("query", "expected_msg"),
        [
            pytest.param("error=access_denied", "access_denied", id="refused"),
            pytest.param("", "no authorisation code received", id="no_code"),
        ],
    )
    async def test__complete__authorization_error(
        self,
        mock_auth_state_repository: mock.AsyncMock,
        mock_provider_oauth: mock.AsyncMock,
        connect_start: ConnectStart,
        query: str,
        expected_msg: str,
    ) -> None:
        auth_state = OAuthProviderStateFactory.build(user_id=connect_start.user.id, provider=connect_start.provider)
        mock_auth_state_repository.consume.return_value = auth_state

        with pytest.raises(ProviderOAuthAuthorizationError, match=expected_msg):
            await provider_connect_complete_logic(
                connect_start,
                f"http://127.0.0.1:65535/cli/callback?{query}&state={auth_state.state}",
            )

        # Single use: a refused consent consumes the state too.
        mock_auth_state_repository.consume.assert_awaited_once_with(state=auth_state.state)
        mock_provider_oauth.exchange_code_for_token.assert_not_awaited()
