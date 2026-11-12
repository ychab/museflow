from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.enums import LLMOperation
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
            email="test@example.com", group_by=[LLMUsageGroupBy.OPERATION], operation=None, since=None, until=None
        )

    def test__all_users(self, runner: CliRunner, mock_llm_usage_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["llm", "usage", "--by", "user"])
        assert result.exit_code == 0
        mock_llm_usage_logic.assert_awaited_once_with(
            email=None, group_by=[LLMUsageGroupBy.USER], operation=None, since=None, until=None
        )

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
            app,
            [
                "llm",
                "usage",
                "--email",
                "test@example.com",
                "--operation",
                "enrich",
                "--since",
                "2026-11-01",
                "--until",
                "2026-11-01",
                "--by",
                "model",
                "--by",
                "effort",
            ],
        )
        assert result.exit_code == 0
        mock_llm_usage_logic.assert_awaited_once_with(
            email="test@example.com",
            group_by=[LLMUsageGroupBy.MODEL, LLMUsageGroupBy.EFFORT],
            operation=LLMOperation.ENRICH,
            since=date(2026, 11, 1),
            until=date(2026, 11, 1),
        )

    def test__by__repeated(
        self,
        runner: CliRunner,
        mock_llm_usage_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["llm", "usage", "--by", "model", "--by", "effort", "--by", "model"])
        assert result.exit_code != 0
        assert "each --by may only be given once" in clean_typer_text(result.output)
        mock_llm_usage_logic.assert_not_awaited()

    def test__until__before_since(
        self,
        runner: CliRunner,
        mock_llm_usage_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["llm", "usage", "--since", "2026-11-02", "--until", "2026-11-01"])
        assert result.exit_code != 0
        assert "--until is before --since" in clean_typer_text(result.output)
        mock_llm_usage_logic.assert_not_awaited()

    def test__operation__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["llm", "usage", "--operation", "rate"])
        assert result.exit_code != 0
        assert "Invalid value for '--operation'" in clean_typer_text(result.output)

    def test__by__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com", "--by", "day"])
        assert result.exit_code != 0
        assert "Invalid value for '--by'" in clean_typer_text(result.output)

    @pytest.mark.parametrize("option", ["--since", "--until"])
    def test__date__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner, option: str) -> None:
        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com", option, "01/11/2026"])
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
                    values=["evening", "enricher"],
                    totals=LLMUsageTotals(
                        runs=2,
                        calls=6,
                        prompt_tokens=12000,
                        completion_tokens=3000,
                        reasoning_tokens=1000,
                        cost=Decimal("0.13"),
                    ),
                ),
                LLMUsageGroup(values=[None, "advisor"], totals=LLMUsageTotals(runs=1, calls=1, cost=Decimal("0.01"))),
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

        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com", "--by", "profile", "--by", "step"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert "┃ Profile ┃ Step ┃ Runs ┃" in output
        assert "evening enricher 2 6 12,000 3,000 1,000 $0.1300" in output
        assert "(none) advisor 1 1 0 0 0 $0.0100" in output
        assert "Total 3 7 12,000 3,000 1,000 $0.1400" in output

    def test__groups__by_run(
        self, runner: CliRunner, mock_llm_usage_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        # One run per row: no Runs column, the total still counts them.
        mock_llm_usage_logic.return_value = LLMUsageSummary(
            groups=[
                LLMUsageGroup(values=["2026-11-02 09:30:00"], totals=LLMUsageTotals(runs=1, calls=4)),
                LLMUsageGroup(values=["2026-11-03 10:00:00"], totals=LLMUsageTotals(runs=1, calls=5)),
            ],
            total=LLMUsageTotals(runs=2, calls=9),
        )

        result = runner.invoke(app, ["llm", "usage", "--email", "test@example.com", "--by", "run"])

        assert result.exit_code == 0
        output = clean_typer_text(result.output)
        assert "┃ Run ┃ Calls ┃" in output
        assert "Runs" not in output
        assert "2026-11-02 09:30:00 4 0 0 0 $0.0000" in output
        assert "Total (2 runs) 9 0 0 0 $0.0000" in output

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
            await llm_usage_logic(
                email="unknown@example.com",
                group_by=[LLMUsageGroupBy.OPERATION],
                operation=None,
                since=None,
                until=None,
            )
