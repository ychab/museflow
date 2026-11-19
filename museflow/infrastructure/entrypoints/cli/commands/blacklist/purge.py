from pydantic import EmailStr

import typer

from museflow.application.use_cases.blacklist_remove import RemoveFromBlacklistUseCase
from museflow.application.use_cases.user_get import get_user
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.blacklist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION


@app.command("purge", help="Delete your entire blacklist. This cannot be undone.")
def blacklist_purge_command(
    email: str = EMAIL_OPTION,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    if not yes and not typer.confirm(
        typer.style(f"Delete the entire blacklist of {email}? This cannot be undone.", fg=typer.colors.YELLOW)
    ):
        raise typer.Abort()

    try:
        count = run_logic(blacklist_purge_logic(email=email))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"Deleted {count} blacklist {'entry' if count == 1 else 'entries'} of {email}.", fg=typer.colors.GREEN)


async def blacklist_purge_logic(email: EmailStr) -> int:
    uow = get_wiring().build_unit_of_work()

    user = await get_user(email=email, uow=uow)

    use_case = RemoveFromBlacklistUseCase(uow=uow)
    return await use_case.purge(user_id=user.id)
