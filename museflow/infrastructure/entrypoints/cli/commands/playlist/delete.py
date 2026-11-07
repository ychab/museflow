import asyncio
import uuid
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.use_cases.playlist_delete import DeletePlaylistUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION


@app.command(
    "delete",
    help="Delete a playlist. Pass --include-remote to also unfollow it on the provider (e.g. Spotify).",
)
def playlist_delete_command(
    playlist_id: uuid.UUID | None = typer.Argument(None, help="Playlist ID (required unless --purge is used)"),
    email: str = EMAIL_OPTION,
    purge: bool = typer.Option(False, "--purge", help="Delete all matching playlists instead of a single one"),
    type: PlaylistType | None = typer.Option(None, "--type", help="Filter by playlist type (only valid with --purge)"),
    provider: MusicProvider | None = typer.Option(
        None, "--provider", help="Filter by provider (only valid with --purge)"
    ),
    include_remote: bool = typer.Option(
        False, "--include-remote", help="Also unfollow/delete the playlist on the provider (e.g. Spotify)"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    if purge:
        if playlist_id is not None:
            raise typer.BadParameter("Provide either a playlist ID or --purge, not both.")
        if not yes:
            scope = ", ".join(
                f"{key}={value.value}" for key, value in (("type", type), ("provider", provider)) if value is not None
            )
            suffix = f" ({scope})" if scope else ""
            typer.confirm(
                f"About to delete ALL playlists{suffix} of {email}. This cannot be undone. Continue?", abort=True
            )
    elif playlist_id is None:
        raise typer.BadParameter("Provide a playlist ID, or use --purge to delete multiple playlists.")
    elif type is not None or provider is not None:
        raise typer.BadParameter("--type and --provider can only be used with --purge.")

    try:
        count = asyncio.run(
            playlist_delete_logic(
                email=email,
                playlist_id=playlist_id,
                purge=purge,
                type=type,
                provider=provider,
                include_remote=include_remote,
            )
        )
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except PlaylistNotFoundError as e:
        typer.secho(f"Playlist {playlist_id} not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except ProviderAuthTokenNotFoundError as e:
        typer.secho(f"Auth token not found for {email}. Did you forget to connect?", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"Deleted {count} playlist(s) of {email}.", fg=typer.colors.GREEN)


async def playlist_delete_logic(
    email: EmailStr,
    playlist_id: uuid.UUID | None,
    purge: bool,
    type: PlaylistType | None,
    provider: MusicProvider | None,
    include_remote: bool = False,
) -> int:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)
        if not user:
            raise UserNotFoundError()

    use_case = DeletePlaylistUseCase(user_id=user.id, uow=uow)

    if not include_remote:
        if purge:
            return await use_case.purge(type=type, provider=provider)

        await use_case.delete(playlist_id=playlist_id)  # type: ignore[arg-type]
        return 1

    if purge:
        playlists = await use_case.find_matching(type=type, provider=provider)
    else:
        playlists = [await use_case.find(playlist_id=playlist_id)]  # type: ignore[arg-type]

    async with AsyncExitStack() as stack:
        provider_libraries = {
            playlist_provider: await stack.enter_async_context(
                get_provider_library(playlist_provider, user=user, uow=uow)
            )
            for playlist_provider in {playlist.provider for playlist in playlists}
        }

        if purge:
            return await use_case.purge_remote(playlists=playlists, provider_libraries=provider_libraries)

        await use_case.delete_remote(playlist=playlists[0], provider_libraries=provider_libraries)
        return 1
