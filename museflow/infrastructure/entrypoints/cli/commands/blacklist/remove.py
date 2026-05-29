import asyncio
import uuid
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.use_cases.remove_from_blacklist import RemoveFromBlacklistUseCase
from museflow.domain.exceptions import BlacklistItemNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.blacklist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_blacklist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("remove", help="Remove one or more blacklist entries by their ID.")
def remove(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    item_ids: list[uuid.UUID] = typer.Argument(..., help="Blacklist entry ID(s) (from `muse blacklist list`)"),
) -> None:
    try:
        asyncio.run(remove_logic(email=email, item_ids=item_ids))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except BlacklistItemNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


async def remove_logic(email: EmailStr, item_ids: list[uuid.UUID]) -> None:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        user = await get_user_repository(session).get_by_email(email)
        if not user:
            raise UserNotFound()

        use_case = RemoveFromBlacklistUseCase(blacklist_repository=get_blacklist_repository(session))
        await use_case.remove(user_id=user.id, item_ids=item_ids)

        typer.secho(f"Removed {len(item_ids)} blacklist entry(ies).", fg=typer.colors.GREEN)
