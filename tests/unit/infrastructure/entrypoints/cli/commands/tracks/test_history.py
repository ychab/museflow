from collections.abc import Iterable
from pathlib import Path
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.use_cases.track_history_import import ImportStreamingHistoryReport
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import StreamingHistoryFilesNotFoundError
from museflow.domain.exceptions import StreamingHistoryInvalidFormatError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.tracks.history import tracks_history_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestTracksHistoryParserCommand:
    @pytest.fixture(autouse=True)
    def mock_tracks_history_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.tracks.history.tracks_history_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner, tmp_path: Path) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "tracks", "history",
                "--email", "test@example.com",
                "--directory", str(tmp_path),
                "--min-duration-played", "10",
                "--batch-size", "50",
                "--purge",
            ],
        )
        # fmt: on
        assert result.exit_code == 0

    def test__provider__explicit(self, runner: CliRunner, tmp_path: Path) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "tracks", "history",
                "--email", "test@example.com",
                "--directory", str(tmp_path),
                "--provider", "spotify",
            ],
        )
        # fmt: on
        assert result.exit_code == 0

    def test__directory__not_found(self, runner: CliRunner, tmp_path: Path, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["tracks", "history", "--email", "test@example.com", "--directory", str(tmp_path / "nonexistent")],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert "Invalid value for '--directory'" in output
        assert "does not exist" in output

    def test__provider__invalid(self, runner: CliRunner, tmp_path: Path) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "tracks", "history",
                "--email", "test@example.com",
                "--directory", str(tmp_path),
                "--provider", "deezer",
            ],
        )
        # fmt: on
        assert result.exit_code != 0

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
        tmp_path: Path,
    ) -> None:
        result = runner.invoke(app, ["tracks", "history", "--email", email, "--directory", str(tmp_path)])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output

    @pytest.mark.parametrize(
        ("batch_size", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--batch-size': Input should be greater than or equal to 1", id="zero"),
            pytest.param(
                -15, "Invalid value for '--batch-size': Input should be greater than or equal to 1", id="min_exceed"
            ),
            pytest.param(
                1000, "Invalid value for '--batch-size': Input should be less than or equal to 500", id="max_exceed"
            ),
            pytest.param("foo", "Invalid value for '--batch-size': Input should be a valid integer", id="string"),
        ],
    )
    def test__batch_size__invalid(
        self,
        runner: CliRunner,
        batch_size: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "tracks", "history",
                "--email", "test@example.com",
                "--directory", str(tmp_path),
                "--batch-size", batch_size,
            ],
        )
        # fmt: on
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output


class TestTracksHistoryCommand:
    @pytest.fixture(autouse=True)
    def mock_tracks_history_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.tracks.history.tracks_history_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_tracks_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        mock_tracks_history_logic.side_effect = UserNotFoundError()

        result = runner.invoke(
            app,
            ["tracks", "history", "--email", "test@example.com", "--directory", str(tmp_path)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__files_not_found(
        self,
        mock_tracks_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        mock_tracks_history_logic.side_effect = StreamingHistoryFilesNotFoundError(
            "No Streaming_History_Audio_*.json files found in: /bad/path"
        )

        result = runner.invoke(
            app,
            ["tracks", "history", "--email", "test@example.com", "--directory", str(tmp_path)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "No Streaming_History_Audio_*.json files found in: /bad/path" in output

    def test__generic_exception(
        self,
        mock_tracks_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        mock_tracks_history_logic.side_effect = Exception("Boom")

        result = runner.invoke(
            app,
            ["tracks", "history", "--email", "test@example.com", "--directory", str(tmp_path)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__nominal__output(
        self,
        mock_tracks_history_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        tmp_path: Path,
    ) -> None:
        mock_tracks_history_logic.return_value = ImportStreamingHistoryReport(
            items_read=1000,
            items_skipped_no_timestamp=5,
            items_skipped_short_play=200,
            items_skipped_no_track_id=50,
            unique_track_ids=750,
            tracks_already_known=300,
            tracks_created=200,
        )

        result = runner.invoke(
            app,
            ["tracks", "history", "--email", "test@example.com", "--directory", str(tmp_path)],
        )
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Import successful in" in output
        assert "Items read 1000" in output
        assert "Items skipped (no timestamp) 5" in output
        assert "Items skipped (short play) 200" in output
        assert "Items skipped (no track ID) 50" in output
        assert "Unique track IDs 750" in output
        assert "Tracks already known 300" in output
        assert "Tracks created 200" in output


@pytest.mark.usefixtures(
    "mock_wiring",
    "mock_user_repository",
    "mock_track_repository",
)
class TestTracksHistoryLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.tracks.history"
    PREFIX: Final[str] = "history/batch"

    @pytest.fixture(autouse=True)
    def mock_build_adapters(
        self,
        mock_wiring: mock.MagicMock,
        mock_streaming_history: mock.AsyncMock,
        mock_file_storage: mock.AsyncMock,
    ) -> None:
        mock_wiring.build_streaming_history.return_value = mock_streaming_history
        mock_wiring.build_file_storage.return_value = mock_file_storage

    @pytest.fixture
    def mock_use_case_cls(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.ImportStreamingHistoryUseCase") as patched:
            patched.return_value.import_history = mock.AsyncMock(return_value=ImportStreamingHistoryReport())
            yield patched

    @pytest.fixture
    def history_dir(self, tmp_path: Path) -> Path:
        (tmp_path / "Streaming_History_Audio_0.json").write_text("[]")
        return tmp_path

    async def test__user__not_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_progress: mock.AsyncMock,
        history_dir: Path,
    ) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await tracks_history_logic(
                progress=mock_progress,
                email="test@example.com",
                directory=history_dir,
                config=ImportStreamingHistoryConfigInput(prefix=self.PREFIX),
                provider=MusicProvider.SPOTIFY,
            )

    async def test__files__not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_file_storage: mock.AsyncMock,
        mock_progress: mock.AsyncMock,
        tmp_path: Path,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        (tmp_path / "Streaming_History_Video_2020.json").write_text("[]")

        with pytest.raises(
            StreamingHistoryFilesNotFoundError, match="No Streaming_History_Audio_\\*.json files found in"
        ):
            await tracks_history_logic(
                progress=mock_progress,
                email=user.email,
                directory=tmp_path,
                config=ImportStreamingHistoryConfigInput(prefix=self.PREFIX),
                provider=MusicProvider.SPOTIFY,
            )

        mock_file_storage.put.assert_not_awaited()

    async def test__import__error__files_deleted(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_file_storage: mock.AsyncMock,
        mock_use_case_cls: mock.Mock,
        mock_progress: mock.AsyncMock,
        history_dir: Path,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_use_case_cls.return_value.import_history.side_effect = StreamingHistoryInvalidFormatError("Invalid file")

        with pytest.raises(StreamingHistoryInvalidFormatError):
            await tracks_history_logic(
                progress=mock_progress,
                email=user.email,
                directory=history_dir,
                config=ImportStreamingHistoryConfigInput(prefix=self.PREFIX),
                provider=MusicProvider.SPOTIFY,
            )

        mock_file_storage.delete.assert_awaited_once_with(user_id=user.id, prefix=self.PREFIX)
