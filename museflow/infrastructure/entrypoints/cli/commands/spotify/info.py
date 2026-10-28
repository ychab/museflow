import asyncio
from dataclasses import asdict

from pydantic import EmailStr

import typer
from rich.pretty import Pretty

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.spotify import app
from museflow.infrastructure.entrypoints.cli.commands.spotify import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("info", help="Show the stored Spotify auth token of a user.")
def info(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
) -> None:
    try:
        token = asyncio.run(info_logic(email=email))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if token:
        console.print("Spotify Auth Token:")
        console.print(Pretty(asdict(token)), soft_wrap=True)


async def info_logic(email: EmailStr) -> OAuthProviderUserToken | None:
    async with get_unit_of_work() as uow:
        user = await uow.users.get_by_email(email)
        if user is None:
            raise UserNotFound(f"User with email '{email}' not found.")

        return await uow.auth_tokens.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
