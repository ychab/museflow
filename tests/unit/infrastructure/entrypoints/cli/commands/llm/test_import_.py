from collections.abc import Iterable
from pathlib import Path
from typing import Final
from unittest import mock

from pydantic import ValidationError

import pytest
from typer.testing import CliRunner

from museflow.application.use_cases.llm_usage_import import ImportLLMUsageResult
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.llm.import_ import llm_import_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.llm.import_"


@pytest.fixture
def llm_usage_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "llm-usage.yaml"
    path.write_text("- step: advisor\n")
    return path


class TestLlmImportParserCommand:
    @pytest.fixture(autouse=True)
    def mock_llm_import_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.llm_import_logic", autospec=True) as patched:
            patched.return_value = ImportLLMUsageResult(imported_count=0, skipped_count=0)
            yield patched

    @pytest.mark.parametrize(
        ("email", "expected_msg"),
        [
            pytest.param("testtest.com", "An email address must have an @-sign", id="missing_@"),
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
        llm_usage_yaml: Path,
    ) -> None:
        result = runner.invoke(app, ["llm", "import", "--email", email, "--input", str(llm_usage_yaml)])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output


class TestLlmImportCommand:
    @pytest.fixture(autouse=True)
    def mock_llm_import_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.llm_import_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_llm_import_logic: mock.AsyncMock,
        runner: CliRunner,
        llm_usage_yaml: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_llm_import_logic.side_effect = UserNotFoundError()

        result = runner.invoke(app, ["llm", "import", "--email", "test@example.com", "--input", str(llm_usage_yaml)])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_llm_import_logic: mock.AsyncMock,
        runner: CliRunner,
        llm_usage_yaml: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_llm_import_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["llm", "import", "--email", "test@example.com", "--input", str(llm_usage_yaml)])
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__nominal(
        self,
        mock_llm_import_logic: mock.AsyncMock,
        runner: CliRunner,
        llm_usage_yaml: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_llm_import_logic.return_value = ImportLLMUsageResult(imported_count=3, skipped_count=2)

        result = runner.invoke(app, ["llm", "import", "--email", "test@example.com", "--input", str(llm_usage_yaml)])
        assert result.exit_code == 0

        output = clean_typer_text(result.output)
        assert "Imported 3 LLM usage row(s) (2 already there)." in output
        assert mock_llm_import_logic.call_args.kwargs["data"] == [{"step": "advisor"}]


@pytest.mark.usefixtures("mock_get_unit_of_work", "mock_user_repository")
class TestLlmImportLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(None, id="empty_file"),
            pytest.param({"step": "advisor"}, id="mapping"),
            pytest.param([{"step": "advisor"}], id="missing_fields"),
        ],
    )
    async def test__invalid_data(self, data: object) -> None:
        with pytest.raises(ValidationError):
            await llm_import_logic(email="test@example.com", data=data)

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await llm_import_logic(email="test@example.com", data=[])
