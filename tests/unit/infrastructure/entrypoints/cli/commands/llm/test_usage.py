from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.enums import LLMUsageGroupBy
from museflow.domain.exceptions import UserNotFoundError
from museflow.domain.value_objects.llm import LLMUsageGroup
from museflow.domain.value_objects.llm import LLMUsageSummary
from museflow.domain.value_objects.llm import LLMUsageTotals
from museflow.infrastructure.entrypoints.cli.commands.llm.usage import llm_usage_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.llm.usage"


class TestLLMUsageParserCommand:
    @pytest.fixture(autouse=True)
    def mock_llm_usage_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.llm_usage_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = LLMUsageSummary(groups=[], total=LLMUsageTotals())
            yield patched

    def test__defaults(self, runner: CliRunner, mock_llm_usage_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com"])
        assert result.exit_code == 0
        mock_llm_usage_logic.assert_awaited_once_with(
            email="test@example.com", group_by=LLMUsageGroupBy.OPERATION, since=None
        )

    def test__all_users(self, runner: CliRunner, mock_llm_usage_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["llm", "usage", "--by", "user"])
        assert result.exit_code == 0
        mock_llm_usage_logic.assert_awaited_once_with(email=None, group_by=LLMUsageGroupBy.USER, since=None)

    def test__by_user__with_email(
        self,
        runner: CliRunner,
        mock_llm_usage_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com", "--by", "user"])
        assert result.exit_code != 0
        assert "--by user sums all the users: drop --email" in clean_typer_text(result.output)
        mock_llm_usage_logic.assert_not_awaited()

    def test__options(self, runner: CliRunner, mock_llm_usage_logic: mock.AsyncMock) -> None:
        result = runner.invoke(
            app, ["llm", "usage", "--email", "test@example.com", "--by", "month", "--since", "2026-11-01"]
        )
        assert result.exit_code == 0
        mock_llm_usage_logic.assert_awaited_once_with(
            email="test@example.com", group_by=LLMUsageGroupBy.MONTH, since=date(2026, 11, 1)
        )

    def test__by__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com", "--by", "day"])
        assert result.exit_code != 0
        assert "Invalid value for '--by'" in clean_typer_text(result.output)

    def test__since__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com", "--since", "01/11/2026"])
        assert result.exit_code != 0
        assert "Date must be in YYYY-MM-DD format" in clean_typer_text(result.output)

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["llm", "usage", "--email", "testtest.com"])
        assert result.exit_code != 0
        assert "An email address must have an @-sign" in clean_typer_text(result.output)


class TestLLMUsageCommand:
    @pytest.fixture(autouse=True)
    def mock_llm_usage_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.llm_usage_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = LLMUsageSummary(groups=[], total=LLMUsageTotals())
            yield patched

    def test__empty(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "No LLM usage recorded." in result.output

    def test__groups(
        self, runner: CliRunner, mock_llm_usage_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_llm_usage_logic.return_value = LLMUsageSummary(
            groups=[
                LLMUsageGroup(
                    name="evening",
                    totals=LLMUsageTotals(
                        runs=2,
                        calls=6,
                        prompt_tokens=12000,
                        completion_tokens=3000,
                        reasoning_tokens=1000,
                        cost=Decimal("0.13"),
                    ),
                ),
                LLMUsageGroup(name=None, totals=LLMUsageTotals(runs=1, calls=1, cost=Decimal("0.01"))),
            ],
            total=LLMUsageTotals(
                runs=3,
                calls=7,
                prompt_tokens=12000,
                completion_tokens=3000,
                reasoning_tokens=1000,
                cost=Decimal("0.14"),
            ),
        )

        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com", "--by", "profile"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert "Profile" in output
        assert "evening 2 6 12,000 3,000 1,000 $0.1300" in output
        assert "(none) 1 1 0 0 0 $0.0100" in output
        assert "Total 3 7 12,000 3,000 1,000 $0.1400" in output

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_llm_usage_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_llm_usage_logic.side_effect = UserNotFoundError()
        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exceptions(
        self, runner: CliRunner, mock_llm_usage_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_llm_usage_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_unit_of_work", "mock_user_repository")
class TestLLMUsageLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFoundError):
            await llm_usage_logic(email="unknown@example.com", group_by=LLMUsageGroupBy.OPERATION, since=None)
