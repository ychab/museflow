import uuid
from collections.abc import Iterable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final
from unittest import mock

import pytest
import yaml
from typer.testing import CliRunner

from museflow.application.inputs.llm import LLMUsageEntryInput
from museflow.domain.enums import LLMOperation
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.llm.export import llm_export_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.llm.export"


class TestLlmExportParserCommand:
    @pytest.fixture(autouse=True)
    def mock_llm_export_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.llm_export_logic", autospec=True) as patched:
            patched.return_value = []
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
        tmp_path: Path,
    ) -> None:
        result = runner.invoke(app, ["llm", "export", "--email", email, "--output", str(tmp_path / "out.yaml")])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output


class TestLlmExportCommand:
    @pytest.fixture(autouse=True)
    def mock_llm_export_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.llm_export_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_llm_export_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_llm_export_logic.side_effect = UserNotFoundError()

        result = runner.invoke(
            app,
            ["llm", "export", "--email", "test@example.com", "--output", str(tmp_path / "out.yaml")],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_llm_export_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_llm_export_logic.side_effect = Exception("Boom")

        result = runner.invoke(
            app,
            ["llm", "export", "--email", "test@example.com", "--output", str(tmp_path / "out.yaml")],
        )
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__nominal(
        self,
        mock_llm_export_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        run_id = uuid.uuid4()
        mock_llm_export_logic.return_value = [
            LLMUsageEntryInput(
                run_id=run_id,
                operation=LLMOperation.DISCOVER,
                profile_name="my-profile",
                step="advisor",
                model="google/gemini-3.5-flash",
                calls=2,
                prompt_tokens=5000,
                completion_tokens=6000,
                reasoning_tokens=4000,
                cost=Decimal("0.0624"),
                duration=timedelta(seconds=30),
                created_at=datetime(2026, 11, 8, 15, 16, tzinfo=UTC),
            )
        ]
        output_path = tmp_path / "out.yaml"

        result = runner.invoke(app, ["llm", "export", "--email", "test@example.com", "--output", str(output_path)])
        assert result.exit_code == 0

        output = clean_typer_text(result.output)
        assert f"Exported 1 LLM usage row(s) to {output_path}" in output
        [entry] = yaml.safe_load(output_path.read_text())
        assert entry["run_id"] == str(run_id)
        assert entry["profile_name"] == "my-profile"
        assert entry["cost"] == "0.0624"


@pytest.mark.usefixtures("mock_get_unit_of_work", "mock_user_repository")
class TestLlmExportLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await llm_export_logic(email="test@example.com")
