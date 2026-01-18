from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from spotifagent.application.services.spotify import TimeRange
from spotifagent.application.use_cases.spotify_sync_top_items import spotify_sync_top_items
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_db
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_spotify_client
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_spotify_user_session_factory
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_top_artist_repository
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_top_track_repository
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_user_repository


async def sync_top_items_logic(
    email: EmailStr,
    purge_top_artists: bool = False,
    purge_top_tracks: bool = False,
    sync_top_artists: bool = False,
    sync_top_tracks: bool = False,
    page_limit: int = 50,
    time_range: TimeRange = "long_term",
    batch_size: int = 300,
) -> None:
    if not any([purge_top_artists, purge_top_tracks, sync_top_artists, sync_top_tracks]):
        typer.secho("At least one flag must be provided.", fg=typer.colors.RED, err=True)
        raise typer.Abort()

    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        spotify_client = await stack.enter_async_context(get_spotify_client())
        spotify_session_factory = get_spotify_user_session_factory(
            session=session,
            spotify_client=spotify_client,
        )

        user_repository = get_user_repository(session)
        top_artist_repository = get_top_artist_repository(session)
        top_track_repository = get_top_track_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise typer.BadParameter(f"User not found with email: {email}")

        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=spotify_session_factory,
            top_artist_repository=top_artist_repository,
            top_track_repository=top_track_repository,
            purge_top_artists=purge_top_artists,
            purge_top_tracks=purge_top_tracks,
            sync_top_artists=sync_top_artists,
            sync_top_tracks=sync_top_tracks,
            page_limit=page_limit,
            time_range=time_range,
            batch_size=batch_size,
        )

        if report.has_errors:
            for error in report.errors:
                typer.secho(error, fg=typer.colors.RED, err=True)
            raise typer.Abort()

        typer.secho("\nSynchronization successful!\n", fg=typer.colors.GREEN)

        if purge_top_artists:
            typer.secho(f"- {report.purge_top_artist} top artists purged", fg=typer.colors.GREEN)
        if purge_top_tracks:
            typer.secho(f"- {report.purge_top_track} top tracks purged", fg=typer.colors.GREEN)

        if sync_top_artists:
            typer.secho(f"- {report.top_artist_created} top artists created", fg=typer.colors.GREEN)
            typer.secho(f"- {report.top_artist_updated} top artists updated", fg=typer.colors.GREEN)
        if sync_top_tracks:
            typer.secho(f"- {report.top_track_created} top tracks created", fg=typer.colors.GREEN)
            typer.secho(f"- {report.top_track_updated} top tracks updated", fg=typer.colors.GREEN)
