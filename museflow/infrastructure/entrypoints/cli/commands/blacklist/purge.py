import asyncio

from pydantic import EmailStr

import typer

from museflow.application.use_cases.blacklist_remove import RemoveFromBlacklistUseCase
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.blacklist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("purge", help="Delete your entire blacklist. This cannot be undone.")
def purge(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    if not yes and not typer.confirm("Delete your entire blacklist? This cannot be undone."):
        raise typer.Abort()

    try:
        count = asyncio.run(purge_logic(email=email))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"Deleted {count} blacklist {'entry' if count == 1 else 'entries'}.", fg=typer.colors.GREEN)


async def purge_logic(email: EmailStr) -> int:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)

    if not user:
        raise UserNotFound()

    use_case = RemoveFromBlacklistUseCase(uow=uow)
    return await use_case.purge(user_id=user.id)
