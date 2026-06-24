import asyncio
from contextlib import AsyncExitStack
from datetime import date

from pydantic import EmailStr

import typer
from rich.console import Console
from rich.table import Table

from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.application.use_cases.playlist_history import playlist_history as playlist_history_use_case
from museflow.domain.entities.playlist import Playlist
from museflow.domain.exceptions import PlaylistNoTracksError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.domain.types import PlaylistHistoryOrderBy
from museflow.infrastructure.entrypoints.cli.commands.playlist import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_playlist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_date
from museflow.infrastructure.entrypoints.cli.parsers import parse_email

console = Console()


@app.command("history")
def playlist_history(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    provider: MusicProvider = typer.Option(default=MusicProvider.SPOTIFY, help="The music provider to use"),
    name_suffix: str | None = typer.Option(
        None, "--name-suffix", help="Custom name suffix for the playlist (replaces the timestamp)"
    ),
    score_min: int | None = typer.Option(None, "--score-min", help="Minimum track score (0-10)", min=0, max=10),
    score_max: int | None = typer.Option(None, "--score-max", help="Maximum track score (0-10)", min=0, max=10),
    artist: str | None = typer.Option(None, "--artist", help="Filter by primary artist name"),
    played_first_min: date | None = typer.Option(
        None,
        "--played-first-min",
        help="Filter tracks first played on or after this date (YYYY-MM-DD)",
        parser=parse_date,
    ),
    played_first_max: date | None = typer.Option(
        None,
        "--played-first-max",
        help="Filter tracks first played on or before this date (YYYY-MM-DD)",
        parser=parse_date,
    ),
    played_last_min: date | None = typer.Option(
        None,
        "--played-last-min",
        help="Filter tracks last played on or after this date (YYYY-MM-DD)",
        parser=parse_date,
    ),
    played_last_max: date | None = typer.Option(
        None,
        "--played-last-max",
        help="Filter tracks last played on or before this date (YYYY-MM-DD)",
        parser=parse_date,
    ),
    duplicate: bool = typer.Option(
        False,
        "--duplicate",
        help="Allow tracks already used in a previous history playlist",
    ),
    group_by_artists: bool = typer.Option(False, "--group-by-artists", help="Group tracks by primary artist"),
    sort: PlaylistHistoryOrderBy = typer.Option(
        PlaylistHistoryOrderBy.PLAYED_COUNT, "--sort", help="Sort tracks by this field"
    ),
    limit: int = typer.Option(20, "--limit", help="Maximum number of tracks in the playlist", min=1),
) -> None:
    """Create a playlist from your history tracks, filtered and ordered by play count."""
    if score_min is not None and score_max is not None and score_min > score_max:
        raise typer.BadParameter("--score-min cannot be greater than --score-max")
    if played_first_min is not None and played_first_max is not None and played_first_min > played_first_max:
        raise typer.BadParameter("--played-first-min cannot be after --played-first-max")
    if played_last_min is not None and played_last_max is not None and played_last_min > played_last_max:
        raise typer.BadParameter("--played-last-min cannot be after --played-last-max")

    try:
        playlist = asyncio.run(
            playlist_history_logic(
                email=email,
                provider=provider,
                config=PlaylistHistoryConfigInput(
                    name_suffix=name_suffix,
                    score_min=score_min,
                    score_max=score_max,
                    artist_name=artist,
                    played_first_min=played_first_min,
                    played_first_max=played_first_max,
                    played_last_min=played_last_min,
                    played_last_max=played_last_max,
                    allow_duplicate=duplicate,
                    group_by_artists=group_by_artists,
                    sort_by=sort,
                    limit=limit,
                ),
            ),
        )
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except ProviderAuthTokenNotFoundError as e:
        typer.secho(
            f"Auth token not found with email: {email}. Did you forget to connect?", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(code=1) from e
    except PlaylistNoTracksError as e:
        typer.secho(
            "No history tracks matched the given filters. Try --duplicate if dedup against "
            "previous history playlists is excluding everything.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if group_by_artists:
        typer.secho("Tracks are grouped by primary artist.", fg=typer.colors.BRIGHT_BLACK)

    track_table = Table(title="Tracks added to playlist")
    track_table.add_column("#", justify="right", style="dim")
    track_table.add_column("Artist(s)")
    track_table.add_column("Track")
    track_table.add_column("Played", justify="right")
    track_table.add_column("Score", justify="right")
    for i, track in enumerate(playlist.tracks, start=1):
        artists = ", ".join(track.artists)
        score_str = str(track.score) if track.score is not None else "-"
        track_table.add_row(str(i), artists, track.name, str(track.played_count), score_str)
    console.print(track_table)

    typer.secho(f"\n\nSuccessfully saved into playlist '{playlist.name}'! ✅", fg=typer.colors.GREEN)
    typer.secho(f"Saved playlist ID: {playlist.id}", fg=typer.colors.CYAN)
    typer.secho(f"  View it: museflow playlist view {playlist.id} --email {email}", fg=typer.colors.CYAN)


async def playlist_history_logic(
    email: EmailStr,
    provider: MusicProvider,
    config: PlaylistHistoryConfigInput,
) -> Playlist:
    """Creates a playlist from the user's history tracks.

    Args:
        email: The email of the user.
        provider: The music provider to use for playlist creation.
        config: The filters/limit/dedup configuration for the playlist.

    Returns:
        The created Playlist.

    Raises:
        UserNotFound: If the user with the given email is not found.
        ProviderAuthTokenNotFoundError: If the user's auth token for the provider is not found.
        PlaylistNoTracksError: If no history tracks match the given filters.
    """
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        auth_token_repository = get_auth_token_repository(session)
        track_repository = get_track_repository(session)
        playlist_repository = get_playlist_repository(session)

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        auth_token = await auth_token_repository.get(user_id=user.id, provider=provider)
        if auth_token is None:
            raise ProviderAuthTokenNotFoundError()

        provider_client = await stack.enter_async_context(get_provider_oauth(provider))
        provider_library_factory = get_provider_library_factory(
            provider=provider,
            session=session,
            oauth_client=provider_client,
        )
        provider_library = provider_library_factory.create(user=user, auth_token=auth_token)

        return await playlist_history_use_case(
            user=user,
            config=config,
            track_repository=track_repository,
            playlist_repository=playlist_repository,
            provider_library=provider_library,
        )
