import asyncio
import uuid
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.use_cases.playlist_delete import PlaylistDeleteUseCase
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_playlist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command(
    "delete",
    help="Delete a playlist. Pass --include-remote to also unfollow it on the provider (e.g. Spotify).",
)
def delete(
    playlist_id: uuid.UUID | None = typer.Argument(None, help="Playlist ID (required unless --purge is used)"),
    email: str = typer.Option(..., help="User email address", parser=parse_email),
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
            typer.confirm(f"About to delete ALL playlists{suffix}. This cannot be undone. Continue?", abort=True)
    elif playlist_id is None:
        raise typer.BadParameter("Provide a playlist ID, or use --purge to delete multiple playlists.")
    elif type is not None or provider is not None:
        raise typer.BadParameter("--type and --provider can only be used with --purge.")

    try:
        count = asyncio.run(
            delete_logic(
                email=email,
                playlist_id=playlist_id,
                purge=purge,
                type=type,
                provider=provider,
                include_remote=include_remote,
            )
        )
    except UserNotFound as e:
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

    typer.secho(f"Deleted {count} playlist(s).", fg=typer.colors.GREEN)


async def delete_logic(
    email: EmailStr,
    playlist_id: uuid.UUID | None,
    purge: bool,
    type: PlaylistType | None,
    provider: MusicProvider | None,
    include_remote: bool = False,
) -> int:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user = await get_user_repository(session).get_by_email(email)
        if not user:
            raise UserNotFound()

        playlist_repository = get_playlist_repository(session)
        provider_library = None

        if include_remote:
            auth_token_repository = get_auth_token_repository(session)
            provider_client = await stack.enter_async_context(get_provider_oauth(MusicProvider.SPOTIFY))
            provider_library_factory = get_provider_library_factory(
                provider=MusicProvider.SPOTIFY, session=session, oauth_client=provider_client
            )
            auth_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
            if auth_token is None:
                raise ProviderAuthTokenNotFoundError()
            provider_library = provider_library_factory.create(user=user, auth_token=auth_token)

        use_case = PlaylistDeleteUseCase(
            playlist_repository=playlist_repository,
            provider_library=provider_library,
        )

        if purge:
            return await use_case.purge(user=user, type=type, provider=provider, include_remote=include_remote)

        await use_case.delete(user=user, playlist_id=playlist_id, include_remote=include_remote)  # type: ignore[arg-type]
        return 1
