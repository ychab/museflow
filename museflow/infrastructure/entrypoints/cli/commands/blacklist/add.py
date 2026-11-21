from typing import Annotated

from pydantic import EmailStr

import typer

from museflow.application.use_cases.blacklist_add import AddToBlacklistUseCase
from museflow.application.use_cases.user_get import get_user
from museflow.domain.entities.blacklist import BlacklistedArtist
from museflow.domain.entities.blacklist import BlacklistedTrack
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.blacklist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.options import EmailOption


@app.command("add-artist", help="Add one or more artists to your blacklist.")
def blacklist_add_artist_command(
    email: EmailOption,
    artist_names: Annotated[list[str], typer.Argument(help="Artist name(s) to blacklist")],
) -> None:
    try:
        entries = run_logic(blacklist_add_artist_logic(email=email, artist_names=artist_names))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    for entry in entries:
        typer.secho(f"Blacklisted artist: {entry.artist_name} (id: {entry.id})", fg=typer.colors.GREEN)


async def blacklist_add_artist_logic(email: EmailStr, artist_names: list[str]) -> list[BlacklistedArtist]:
    uow = get_wiring().build_unit_of_work()
    user = await get_user(email=email, uow=uow)

    use_case = AddToBlacklistUseCase(uow=uow)
    return [await use_case.add_artist(user_id=user.id, artist_name=artist_name) for artist_name in artist_names]


@app.command("add-track", help="Add a track to your blacklist.")
def blacklist_add_track_command(
    email: EmailOption,
    name: Annotated[str, typer.Argument(help="Track name")],
    artist: Annotated[str, typer.Option("--artist", help="Artist name")],
) -> None:
    try:
        entry = run_logic(blacklist_add_track_logic(email=email, name=name, artist_name=artist))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(
        f"Blacklisted track: {entry.name} by {entry.artist_name} (id: {entry.id})",
        fg=typer.colors.GREEN,
    )


async def blacklist_add_track_logic(email: EmailStr, name: str, artist_name: str) -> BlacklistedTrack:
    uow = get_wiring().build_unit_of_work()

    user = await get_user(email=email, uow=uow)

    use_case = AddToBlacklistUseCase(uow=uow)
    return await use_case.add_track(user_id=user.id, name=name, artist_name=artist_name)
