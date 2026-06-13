import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.use_cases.blacklist_add import AddToBlacklistUseCase
from museflow.domain.entities.blacklist import BlacklistedArtist
from museflow.domain.entities.blacklist import BlacklistedTrack
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.blacklist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_blacklist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("add-artist", help="Add one or more artists to your blacklist.")
def add_artist(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    artist_names: list[str] = typer.Argument(..., help="Artist name(s) to blacklist"),
) -> None:
    try:
        entries = asyncio.run(add_artists_logic(email=email, artist_names=artist_names))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    for entry in entries:
        typer.secho(f"Blacklisted artist: {entry.artist_name} (id: {entry.id})", fg=typer.colors.GREEN)


async def add_artists_logic(email: EmailStr, artist_names: list[str]) -> list[BlacklistedArtist]:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user = await get_user_repository(session).get_by_email(email)
        if not user:
            raise UserNotFound()

        use_case = AddToBlacklistUseCase(blacklist_repository=get_blacklist_repository(session))

        return [await use_case.add_artist(user_id=user.id, artist_name=artist_name) for artist_name in artist_names]


@app.command("add-track", help="Add a track to your blacklist.")
def add_track(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    name: str = typer.Argument(..., help="Track name"),
    artist: str = typer.Option(..., "--artist", help="Artist name"),
) -> None:
    try:
        entry = asyncio.run(add_track_logic(email=email, name=name, artist_name=artist))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(
        f"Blacklisted track: {entry.name} by {entry.artist_name} (id: {entry.id})",
        fg=typer.colors.GREEN,
    )


async def add_track_logic(email: EmailStr, name: str, artist_name: str) -> BlacklistedTrack:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user = await get_user_repository(session).get_by_email(email)
        if not user:
            raise UserNotFound()

        use_case = AddToBlacklistUseCase(blacklist_repository=get_blacklist_repository(session))
        return await use_case.add_track(user_id=user.id, name=name, artist_name=artist_name)
