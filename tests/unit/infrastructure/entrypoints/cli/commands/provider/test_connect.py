from collections.abc import Iterable
from dataclasses import replace
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.provider.connect import connect_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestProviderConnectParserCommand:
    @pytest.fixture(autouse=True)
    def mock_connect_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.provider.connect.connect_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, mock_connect_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            [
                "provider",
                "connect",
                "--email",
                "test@example.com",
                "--provider",
                "spotify",
                "--timeout",
                "30.0",
                "--poll-interval",
                "0.5",
            ],
        )
        assert result.exit_code == 0
        mock_connect_logic.assert_awaited_once_with("test@example.com", MusicProvider.SPOTIFY, 30.0, 0.5)

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

    @pytest.mark.parametrize(
        ("timeout", "expected_msg"),
        [
            pytest.param(0.0, "Invalid value for '--timeout': 0.0 is not in the range", id="zero"),
            pytest.param(-15.5, "Invalid value for '--timeout': -15.5 is not in the range", id="negative"),
            pytest.param("foo", "Invalid value for '--timeout': 'foo' is not a valid float", id="string"),
        ],
    )
    def test__timeout__invalid(
        self,
        runner: CliRunner,
        timeout: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["provider", "connect", "--email", "test@example.com", "--timeout", timeout],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output

    @pytest.mark.parametrize(
        ("poll_interval", "expected_msg"),
        [
            pytest.param(0.0, "Invalid value for '--poll-interval': 0.0 is not in the range", id="zero"),
            pytest.param(-15.5, "Invalid value for '--poll-interval': -15.5 is not in the range", id="negative"),
            pytest.param("foo", "Invalid value for '--poll-interval': 'foo' is not a valid float", id="string"),
        ],
    )
    def test__poll_interval__invalid(
        self,
        runner: CliRunner,
        poll_interval: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["provider", "connect", "--email", "test@example.com", "--poll-interval", poll_interval],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output


class TestProviderConnectCommand:
    @pytest.fixture(autouse=True)
    def mock_connect_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.provider.connect.connect_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(
        self,
        mock_connect_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Authentication successful!" in output

    def test__user_not_found(
        self,
        mock_connect_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_connect_logic.side_effect = UserNotFound()

        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__timeout__exceed(
        self,
        mock_connect_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_connect_logic.side_effect = TimeoutError()

        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com", "--timeout", "10"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Unable to connect after 10.0 seconds. Did you open your browser and accept?" in output

    def test__exception(
        self,
        mock_connect_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_connect_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures(
    "mock_get_unit_of_work",
    "mock_user_repository",
    "mock_auth_state_repository",
    "mock_auth_token_repository",
    "mock_provider_oauth",
)
class TestProviderConnectLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.provider.connect"

    @pytest.fixture(autouse=True)
    def mock_typer_launch(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.typer.launch") as patched:
            yield patched

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        email = "test@example.com"
        with pytest.raises(UserNotFound):
            await connect_logic(email, MusicProvider.SPOTIFY, 10, 2)

    async def test__failed_flow__no_token(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_auth_state_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        user: User,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        # The callback consumes the state, even when the consent is refused or the code exchange fails.
        mock_auth_state_repository.get.return_value = None
        mock_auth_token_repository.get.return_value = None

        with pytest.raises(TimeoutError):
            await connect_logic(user.email, provider=MusicProvider.SPOTIFY, timeout=0.1, poll_interval=0.05)

    async def test__failed_flow__token_unchanged(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_auth_state_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        user: User,
        auth_token: OAuthProviderUserToken,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_auth_state_repository.get.return_value = None
        mock_auth_token_repository.get.return_value = auth_token

        with pytest.raises(TimeoutError):
            await connect_logic(user.email, provider=MusicProvider.SPOTIFY, timeout=0.1, poll_interval=0.05)

    async def test__token__renewed(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
        user: User,
        auth_token: OAuthProviderUserToken,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_auth_token_repository.get.side_effect = [auth_token, replace(auth_token, token_access="renewed")]

        await connect_logic(user.email, provider=MusicProvider.SPOTIFY, timeout=2.0, poll_interval=0.01)

        assert mock_auth_token_repository.get.await_count == 2
