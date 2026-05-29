import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.use_cases.blacklist_remove import RemoveFromBlacklistUseCase
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.blacklist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_blacklist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
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
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user = await get_user_repository(session).get_by_email(email)
        if not user:
            raise UserNotFound()

        use_case = RemoveFromBlacklistUseCase(blacklist_repository=get_blacklist_repository(session))
        return await use_case.purge(user_id=user.id)
