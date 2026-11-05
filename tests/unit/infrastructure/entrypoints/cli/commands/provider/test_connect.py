import uuid
from collections.abc import Iterable
from dataclasses import replace
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.provider.connect import ConnectStart
from museflow.infrastructure.entrypoints.cli.commands.provider.connect import connect_start_logic
from museflow.infrastructure.entrypoints.cli.commands.provider.connect import connect_wait_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.provider.connect"


@pytest.fixture
def connect_start() -> ConnectStart:
    return ConnectStart(
        user_id=uuid.uuid4(),
        provider=MusicProvider.SPOTIFY,
        previous_token=None,
        authorization_url="http://example.com",
    )


@pytest.fixture
def mock_connect_start_logic(connect_start: ConnectStart) -> Iterable[mock.AsyncMock]:
    with mock.patch(
        f"{TARGET_PATH}.connect_start_logic",
        new_callable=mock.AsyncMock,
        return_value=connect_start,
    ) as patched:
        yield patched


@pytest.fixture
def mock_connect_wait_logic() -> Iterable[mock.AsyncMock]:
    with mock.patch(f"{TARGET_PATH}.connect_wait_logic", new_callable=mock.AsyncMock) as patched:
        yield patched


@pytest.fixture
def mock_typer_launch() -> Iterable[mock.Mock]:
    with mock.patch(f"{TARGET_PATH}.typer.launch") as patched:
        yield patched


@pytest.mark.usefixtures("mock_connect_start_logic", "mock_connect_wait_logic", "mock_typer_launch")
class TestProviderConnectParserCommand:
    def test__nominal(
        self,
        mock_connect_start_logic: mock.AsyncMock,
        mock_connect_wait_logic: mock.AsyncMock,
        connect_start: ConnectStart,
        runner: CliRunner,
    ) -> None:
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
        mock_connect_start_logic.assert_awaited_once_with("test@example.com", MusicProvider.SPOTIFY)
        mock_connect_wait_logic.assert_awaited_once_with(connect_start, 30.0, 0.5)

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


@pytest.mark.usefixtures("mock_connect_start_logic", "mock_connect_wait_logic", "mock_typer_launch")
class TestProviderConnectCommand:
    def test__nominal(
        self,
        mock_typer_launch: mock.Mock,
        connect_start: ConnectStart,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert f"Opening browser for authentication: {connect_start.authorization_url}" in output
        assert "Authentication successful!" in output
        mock_typer_launch.assert_called_once_with(connect_start.authorization_url)

    def test__user_not_found(
        self,
        mock_connect_start_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_connect_start_logic.side_effect = UserNotFound()

        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__timeout__exceed(
        self,
        mock_connect_wait_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_connect_wait_logic.side_effect = TimeoutError()

        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com", "--timeout", "10"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Unable to connect after 10.0 seconds. Did you open your browser and accept?" in output

    def test__exception(
        self,
        mock_connect_start_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_connect_start_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["provider", "connect", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures(
    "mock_get_unit_of_work",
    "mock_user_repository",
    "mock_auth_token_repository",
)
class TestProviderConnectLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__start__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await connect_start_logic("test@example.com", MusicProvider.SPOTIFY)

    async def test__wait__failed_flow__no_token(
        self,
        mock_auth_token_repository: mock.AsyncMock,
        connect_start: ConnectStart,
    ) -> None:
        # The callback consumes the state, even when the consent is refused or the code exchange fails.
        mock_auth_token_repository.get.return_value = None

        with pytest.raises(TimeoutError):
            await connect_wait_logic(connect_start, timeout=0.1, poll_interval=0.05)

    async def test__wait__failed_flow__token_unchanged(
        self,
        mock_auth_token_repository: mock.AsyncMock,
        connect_start: ConnectStart,
        auth_token: OAuthProviderUserToken,
    ) -> None:
        mock_auth_token_repository.get.return_value = auth_token

        with pytest.raises(TimeoutError):
            await connect_wait_logic(
                replace(connect_start, previous_token=auth_token),
                timeout=0.1,
                poll_interval=0.05,
            )

    async def test__wait__token_renewed(
        self,
        mock_auth_token_repository: mock.AsyncMock,
        connect_start: ConnectStart,
        auth_token: OAuthProviderUserToken,
    ) -> None:
        mock_auth_token_repository.get.return_value = replace(auth_token, token_access="renewed")

        await connect_wait_logic(
            replace(connect_start, previous_token=auth_token),
            timeout=2.0,
            poll_interval=0.01,
        )

        mock_auth_token_repository.get.assert_awaited_once()
