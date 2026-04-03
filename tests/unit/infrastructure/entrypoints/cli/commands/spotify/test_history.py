from collections.abc import Iterable
from pathlib import Path
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryReport
from museflow.domain.entities.user import User
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import StreamingHistoryDirectoryNotFound
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.spotify.history import history_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestSpotifyHistoryParserCommand:
    @pytest.fixture(autouse=True)
    def mock_history_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.history.history_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner, tmp_path: Path) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "spotify", "history",
                "--email", "test@example.com",
                "--directory", str(tmp_path),
                "--min-duration-played", "10",
                "--batch-size", "50",
                "--fetch-bulk",
                "--purge",
            ],
        )
        # fmt: on
        assert result.exit_code == 0

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
        result = runner.invoke(app, ["spotify", "history", "--email", email, "--directory", "/tmp"])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output

    @pytest.mark.parametrize(
        ("batch_size", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--batch-size': 0 is not in the range", id="zero"),
            pytest.param(-15, "Invalid value for '--batch-size': -15 is not in the range", id="min_exceed"),
            pytest.param(1000, "Invalid value for '--batch-size': 1000 is not in the range", id="max_exceed"),
            pytest.param("foo", "Invalid value for '--batch-size': 'foo' is not a valid integer", id="string"),
        ],
    )
    def test__batch_size__invalid(
        self,
        runner: CliRunner,
        batch_size: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "spotify", "history",
                "--email", "test@example.com",
                "--directory", "/tmp",
                "--batch-size", batch_size,
            ],
        )
        # fmt: on
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output


class TestSpotifyHistoryCommand:
    @pytest.fixture(autouse=True)
    def mock_history_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.history.history_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        mock_history_logic.side_effect = UserNotFound()

        result = runner.invoke(
            app,
            ["spotify", "history", "--email", "test@example.com", "--directory", str(tmp_path)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__auth_token_not_found(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        mock_history_logic.side_effect = ProviderAuthTokenNotFoundError()

        result = runner.invoke(
            app,
            ["spotify", "history", "--email", "test@example.com", "--directory", str(tmp_path)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Auth token not found with email: test@example.com. Did you forget to connect?" in output

    def test__directory_not_found(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        mock_history_logic.side_effect = StreamingHistoryDirectoryNotFound("Directory not found: /bad/path")

        result = runner.invoke(
            app,
            ["spotify", "history", "--email", "test@example.com", "--directory", str(tmp_path)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Directory not found: /bad/path" in output

    def test__generic_exception(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        mock_history_logic.side_effect = Exception("Boom")

        result = runner.invoke(
            app,
            ["spotify", "history", "--email", "test@example.com", "--directory", str(tmp_path)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__nominal__output(
        self,
        mock_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        mock_history_logic.return_value = ImportStreamingHistoryReport(
            items_read=1000,
            items_skipped_no_ts=5,
            items_skipped_duration=200,
            items_skipped_no_uri=50,
            unique_track_ids=750,
            tracks_already_known=300,
            tracks_fetched=450,
            tracks_created=200,
        )

        result = runner.invoke(
            app,
            ["spotify", "history", "--email", "test@example.com", "--directory", str(tmp_path)],
        )
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Import successful in" in output
        assert "Items read 1000" in output
        assert "Items skipped (no timestamp) 5" in output
        assert "Items skipped (duration) 200" in output
        assert "Items skipped (no URI) 50" in output
        assert "Unique track IDs 750" in output
        assert "Tracks already known 300" in output
        assert "Tracks fetched 450" in output
        assert "Tracks created 200" in output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_auth_token_repository",
    "mock_track_repository",
    "mock_spotify_client",
)
class TestSpotifyHistoryLogicCommand:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.spotify.history"

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await history_logic(
                email="test@example.com",
                config=ImportStreamingHistoryConfigInput(directory=Path("/tmp")),
            )

    async def test__auth_token__not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_auth_token_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_auth_token_repository.get.return_value = None

        with pytest.raises(ProviderAuthTokenNotFoundError):
            await history_logic(
                email=user.email,
                config=ImportStreamingHistoryConfigInput(directory=Path("/tmp")),
            )
