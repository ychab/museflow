from collections.abc import Iterable
from pathlib import Path
from typing import Final
from unittest import mock

from pydantic import ValidationError

import pytest
from typer.testing import CliRunner

from museflow.application.use_cases.ratings_import import ImportRatingsResult
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.rate.import_ import rate_import_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.user import UserFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestRateImportParserCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_import_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.rate.import_.rate_import_logic"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = ImportRatingsResult(
                imported_count=0, skipped_count=0, created_count=0, not_found_count=0
            )
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
    def mock_rate_import_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.rate.import_.rate_import_logic"
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
        mock_rate_import_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_import_logic.side_effect = UserNotFoundError()
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
        mock_rate_import_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_import_logic.side_effect = Exception("Boom")
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
        mock_rate_import_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_import_logic.return_value = ImportRatingsResult(
            imported_count=3, skipped_count=0, created_count=2, not_found_count=1
        )
        valid_yaml = tmp_path / "rates.yaml"
        valid_yaml.write_text("- fingerprint: abc\n  score: 5\n")

        result = runner.invoke(
            app,
            ["rate", "import", "--email", "test@example.com", "--input", str(valid_yaml)],
        )
        assert result.exit_code == 0
        assert (
            "Imported 3 score(s) and 0 permanent skip(s), recreated 2 missing track(s) "
            "(1 fingerprints not found in DB)." in clean_typer_text(result.output)
        )


@pytest.mark.usefixtures(
    "mock_get_unit_of_work",
    "mock_user_repository",
    "mock_track_repository",
)
class TestRateImportLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate.import_"

    async def test__invalid_data(
        self,
        mock_user_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = UserFactory.build()

        with pytest.raises(ValidationError):
            await rate_import_logic(
                email="test@example.com",
                data=[{"fingerprint": "abc", "score": 99}],
            )

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await rate_import_logic(email="test@example.com", data=[])
