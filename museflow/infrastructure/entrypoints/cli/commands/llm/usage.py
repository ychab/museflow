import asyncio
from datetime import date

from pydantic import EmailStr

import typer
from rich.console import Console
from rich.table import Table

from museflow.application.use_cases.llm_usage_summary import summarize_llm_usage
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import LLMUsageGroupBy
from museflow.domain.exceptions import UserNotFoundError
from museflow.domain.value_objects.llm import LLMUsageSummary
from museflow.infrastructure.entrypoints.cli.commands.llm import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_date
from museflow.infrastructure.entrypoints.cli.parsers import parse_email
from museflow.infrastructure.entrypoints.cli.utils.display import format_duration

console = Console()


@app.command(
    "usage",
    help="Show what the LLM calls cost, grouped by operation, model, effort, step, month, profile, user or run.",
)
def llm_usage_command(
    email: str | None = typer.Option(None, help="User email address (all the users when omitted)", parser=parse_email),
    operation: LLMOperation | None = typer.Option(None, "--operation", help="Only the runs of this operation"),
    since: date | None = typer.Option(
        None,
        "--since",
        help="Only the runs from this date on, in UTC (YYYY-MM-DD)",
        parser=parse_date,
    ),
    until: date | None = typer.Option(
        None,
        "--until",
        help="Only the runs up to this date included, in UTC (YYYY-MM-DD)",
        parser=parse_date,
    ),
    group_by: list[LLMUsageGroupBy] | None = typer.Option(
        None,
        "--by",
        help="Group the usage by, repeatable to combine groupings (default: operation)",
    ),
) -> None:
    group_by = group_by or [LLMUsageGroupBy.OPERATION]
    if len(set(group_by)) < len(group_by):
        raise typer.BadParameter("each --by may only be given once")
    if email is not None and LLMUsageGroupBy.USER in group_by:
        raise typer.BadParameter("--by user sums all the users: drop --email")
    if since is not None and until is not None and until < since:
        raise typer.BadParameter("--until is before --since")

    try:
        summary = asyncio.run(
            llm_usage_logic(email=email, group_by=group_by, operation=operation, since=since, until=until)
        )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if not summary.groups:
        typer.secho("No LLM usage recorded.", fg=typer.colors.YELLOW)
        return

    # A run per row with --by run: the Runs column would only show 1, the total keeps the count.
    show_runs = LLMUsageGroupBy.RUN not in group_by
    total = summary.total
    table = Table(title="LLM usage", show_footer=True)
    for index, grouping in enumerate(group_by):
        footer = ""
        if index == 0:
            footer = "Total" if show_runs else f"Total ({total.runs} runs)"
        table.add_column(grouping.value.capitalize(), footer=footer, overflow="fold")
    if show_runs:
        table.add_column("Runs", justify="right", footer=str(total.runs))
    table.add_column("Calls", justify="right", footer=str(total.calls))
    table.add_column("Prompt", justify="right", footer=f"{total.prompt_tokens:,}")
    table.add_column("Completion", justify="right", footer=f"{total.completion_tokens:,}")
    table.add_column("Reasoning", justify="right", footer=f"{total.reasoning_tokens:,}")
    table.add_column("Cost", justify="right", footer=f"${total.cost:.4f}")
    table.add_column("Time", justify="right", footer=format_duration(total.duration))
    for group in summary.groups:
        totals = group.totals
        table.add_row(
            *[value if value is not None else "(none)" for value in group.values],
            *([str(totals.runs)] if show_runs else []),
            str(totals.calls),
            f"{totals.prompt_tokens:,}",
            f"{totals.completion_tokens:,}",
            f"{totals.reasoning_tokens:,}",
            f"${totals.cost:.4f}",
            format_duration(totals.duration),
        )
    console.print(table)


async def llm_usage_logic(
    email: EmailStr | None,
    group_by: list[LLMUsageGroupBy],
    operation: LLMOperation | None,
    since: date | None,
    until: date | None,
) -> LLMUsageSummary:
    uow = get_unit_of_work()

    user_id = None
    if email is not None:
        async with uow:
            user = await uow.users.get_by_email(email)
        if not user:
            raise UserNotFoundError()
        user_id = user.id

    return await summarize_llm_usage(
        user_id=user_id,
        group_by=group_by,
        operation=operation,
        since=since,
        until=until,
        uow=uow,
    )
