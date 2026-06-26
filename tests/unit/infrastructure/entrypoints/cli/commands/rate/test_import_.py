from collections.abc import Iterable
from pathlib import Path
from typing import Final
from unittest import mock

from pydantic import ValidationError

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.rate.import_ import RateImportResult
from museflow.infrastructure.entrypoints.cli.commands.rate.import_ import import_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.factories.entities.user import UserFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestRateImportParserCommand:
    @pytest.fixture(autouse=True)
    def mock_import_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.rate.import_.import_logic"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = RateImportResult(imported_count=0, skipped_count=0, not_found_count=0)
            yield patched

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
        valid_yaml = tmp_path / "rates.yaml"
        valid_yaml.write_text("- fingerprint: abc\n  score: 5\n")

        result = runner.invoke(app, ["rate", "import", "--email", email, "--input", str(valid_yaml)])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output


class TestRateImportCommand:
    @pytest.fixture(autouse=True)
    def mock_import_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.rate.import_.import_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__file_not_found(
        self,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["rate", "import", "--email", "test@example.com", "--input", "/nonexistent/path/rates.yaml"],
        )
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "File not found" in output

    def test__yaml_parse_error(
        self,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [unclosed\n")

        result = runner.invoke(
            app,
            ["rate", "import", "--email", "test@example.com", "--input", str(bad_yaml)],
        )
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Invalid YAML" in output

    def test__user_not_found(
        self,
        mock_import_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_import_logic.side_effect = UserNotFound()
        valid_yaml = tmp_path / "rates.yaml"
        valid_yaml.write_text("- fingerprint: abc\n  score: 5\n")

        result = runner.invoke(
            app,
            ["rate", "import", "--email", "test@example.com", "--input", str(valid_yaml)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_import_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_import_logic.side_effect = Exception("Boom")
        valid_yaml = tmp_path / "rates.yaml"
        valid_yaml.write_text("- fingerprint: abc\n  score: 5\n")

        result = runner.invoke(
            app,
            ["rate", "import", "--email", "test@example.com", "--input", str(valid_yaml)],
        )
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__nominal(
        self,
        mock_import_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        mock_import_logic.return_value = RateImportResult(imported_count=3, skipped_count=0, not_found_count=1)
        valid_yaml = tmp_path / "rates.yaml"
        valid_yaml.write_text("- fingerprint: abc\n  score: 5\n")

        result = runner.invoke(
            app,
            ["rate", "import", "--email", "test@example.com", "--input", str(valid_yaml)],
        )
        assert result.exit_code == 0
        assert "3" in result.output
        assert "1" in result.output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_track_repository",
)
class TestRateImportLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate.import_"

    async def test__fingerprint_not_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = []

        result = await import_logic(
            email="test@example.com",
            data=[{"fingerprint": "unknown-fp", "score": 5}],
        )

        assert result.imported_count == 0
        assert result.not_found_count == 1
        mock_track_repository.rate.assert_not_awaited()

    async def test__invalid_data(
        self,
        mock_user_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = UserFactory.build()

        with pytest.raises(ValidationError):
            await import_logic(
                email="test@example.com",
                data=[{"fingerprint": "abc", "score": 99}],
            )

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await import_logic(email="test@example.com", data=[])

    async def test__score_skipped_entry__calls_skip(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        fingerprint = "test-fingerprint-abc"
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [
            TrackFactory.build(user_id=user.id, fingerprint=fingerprint, score_skipped=False)
        ]

        result = await import_logic(
            email="test@example.com",
            data=[{"fingerprint": fingerprint, "score_skipped": True}],
        )

        mock_track_repository.skip.assert_awaited_once()
        mock_track_repository.rate.assert_not_awaited()
        assert result.skipped_count == 1
        assert result.imported_count == 0

    async def test__entry_with_no_score_and_not_skipped__is_ignored(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        fingerprint = "test-fingerprint-noop"
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.get_list.return_value = [
            TrackFactory.build(user_id=user.id, fingerprint=fingerprint, score_skipped=False)
        ]

        result = await import_logic(
            email="test@example.com",
            data=[{"fingerprint": fingerprint}],
        )

        mock_track_repository.skip.assert_not_awaited()
        mock_track_repository.rate.assert_not_awaited()
        assert result.skipped_count == 0
        assert result.imported_count == 0
        assert result.not_found_count == 0
