import asyncio
from datetime import date

from pydantic import EmailStr

import typer
from rich.console import Console
from rich.table import Table

from museflow.application.use_cases.llm_usage_summary import summarize_llm_usage
from museflow.domain.enums import LLMUsageGroupBy
from museflow.domain.exceptions import UserNotFound
from museflow.domain.value_objects.llm import LLMUsageSummary
from museflow.infrastructure.entrypoints.cli.commands.llm import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_date
from museflow.infrastructure.entrypoints.cli.parsers import parse_email

console = Console()


@app.command(
    "usage",
    help="Show what the LLM calls cost, grouped by operation, model, step, month, profile or user.",
)
def usage_command(
    email: str | None = typer.Option(None, help="User email address (all the users when omitted)", parser=parse_email),
    group_by: LLMUsageGroupBy = typer.Option(LLMUsageGroupBy.OPERATION, "--by", help="Group the usage by"),
    since: date | None = typer.Option(
        None,
        "--since",
        help="Only the runs from this date on, in UTC (YYYY-MM-DD)",
        parser=parse_date,
    ),
) -> None:
    if email is not None and group_by == LLMUsageGroupBy.USER:
        raise typer.BadParameter("--by user sums all the users: drop --email")

    try:
        summary = asyncio.run(usage_logic(email=email, group_by=group_by, since=since))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if not summary.groups:
        typer.secho("No LLM usage recorded.", fg=typer.colors.YELLOW)
        return

    total = summary.total
    table = Table(title="LLM usage", show_footer=True)
    table.add_column(group_by.value.capitalize(), footer="Total", overflow="fold")
    table.add_column("Runs", justify="right", footer=str(total.runs))
    table.add_column("Calls", justify="right", footer=str(total.calls))
    table.add_column("Prompt", justify="right", footer=f"{total.prompt_tokens:,}")
    table.add_column("Completion", justify="right", footer=f"{total.completion_tokens:,}")
    table.add_column("Reasoning", justify="right", footer=f"{total.reasoning_tokens:,}")
    table.add_column("Cost", justify="right", footer=f"${total.cost:.4f}")
    for group in summary.groups:
        totals = group.totals
        table.add_row(
            group.name if group.name is not None else "(none)",
            str(totals.runs),
            str(totals.calls),
            f"{totals.prompt_tokens:,}",
            f"{totals.completion_tokens:,}",
            f"{totals.reasoning_tokens:,}",
            f"${totals.cost:.4f}",
        )
    console.print(table)


async def usage_logic(email: EmailStr | None, group_by: LLMUsageGroupBy, since: date | None) -> LLMUsageSummary:
    uow = get_unit_of_work()

    user_id = None
    if email is not None:
        async with uow:
            user = await uow.users.get_by_email(email)
        if not user:
            raise UserNotFound()
        user_id = user.id

    return await summarize_llm_usage(user_id=user_id, group_by=group_by, since=since, uow=uow)
