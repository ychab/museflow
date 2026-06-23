import asyncio
import uuid
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.use_cases.playlist_delete import playlist_delete
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.domain.types import PlaylistType
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_playlist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command(
    "delete",
    help=(
        "Delete a playlist. Only removes MuseFlow's local record — the playlist itself is not "
        "deleted/unfollowed on the provider (e.g. Spotify)."
    ),
)
def delete(
    playlist_id: uuid.UUID | None = typer.Argument(None, help="Playlist ID (required unless --purge is used)"),
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    purge: bool = typer.Option(False, "--purge", help="Delete all matching playlists instead of a single one"),
    type: PlaylistType | None = typer.Option(None, "--type", help="Filter by playlist type (only valid with --purge)"),
    provider: MusicProvider | None = typer.Option(
        None, "--provider", help="Filter by provider (only valid with --purge)"
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
            typer.confirm(f"About to delete ALL playlists{suffix}. This cannot be undone. Continue?", abort=True)
    elif playlist_id is None:
        raise typer.BadParameter("Provide a playlist ID, or use --purge to delete multiple playlists.")
    elif type is not None or provider is not None:
        raise typer.BadParameter("--type and --provider can only be used with --purge.")

    try:
        count = asyncio.run(
            delete_logic(email=email, playlist_id=playlist_id, purge=purge, type=type, provider=provider)
        )
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except PlaylistNotFoundError as e:
        typer.secho(f"Playlist {playlist_id} not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"Deleted {count} playlist(s).", fg=typer.colors.GREEN)


async def delete_logic(
    email: EmailStr,
    playlist_id: uuid.UUID | None,
    purge: bool,
    type: PlaylistType | None,
    provider: MusicProvider | None,
) -> int:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user = await get_user_repository(session).get_by_email(email)
        if not user:
            raise UserNotFound()

        playlist_repository = get_playlist_repository(session)

        return await playlist_delete(
            user=user,
            playlist_repository=playlist_repository,
            playlist_id=playlist_id,
            purge=purge,
            type=type,
            provider=provider,
        )
