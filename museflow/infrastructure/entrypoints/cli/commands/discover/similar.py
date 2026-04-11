import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer
from rich.table import Table

from museflow.application.inputs.discovery import DiscoverySimilarConfigInput
from museflow.application.use_cases.discover_similar import DiscoverSimilarUseCase
from museflow.application.use_cases.discover_similar import DiscoverySimilarResult
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicAdvisorSimilar
from museflow.domain.types import MusicProvider
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.infrastructure.entrypoints.cli.commands.discover import app
from museflow.infrastructure.entrypoints.cli.commands.discover import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor_similar_adapter
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_reconciler
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("similar", help="Discover new tracks similar to your library seeds.")
def similar(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    advisor: MusicAdvisorSimilar = typer.Option(
        default=MusicAdvisorSimilar.LASTFM, help="The advisor to discover new musics"
    ),
    provider: MusicProvider = typer.Option(default=MusicProvider.SPOTIFY, help="The music provider to use"),
    seed_top: bool | None = typer.Option(
        None,
        "--seed-top/--no-seed-top",
        help="Whether to use a top seed",
    ),
    seed_saved: bool | None = typer.Option(
        None,
        "--seed-saved/--no-seed-saved",
        help="Whether to use a saved seed",
    ),
    seed_genres: list[str] = typer.Option(
        [],
        "--seed-genres",
        help="A list of genres to filter on the seeds",
    ),
    seed_order_by: TrackOrderBy = typer.Option(
        TrackOrderBy.RANDOM,
        "--seed-order-by",
        help="The column seed track to order on",
    ),
    seed_sort_order: SortOrder = typer.Option(
        SortOrder.ASC,
        "--seed-sort-order",
        help="The sort order if the seed tracks",
    ),
    seed_limit: int = typer.Option(
        20,
        "--seed-limit",
        help="The batch size of seed tracks per attempt",
        min=1,
        max=50,
    ),
    similar_limit: int = typer.Option(
        5,
        "--similar-limit",
        help="The limit of similar tracks to fetch",
        min=1,
        max=20,
    ),
    candidate_limit: int = typer.Option(
        10,
        "--candidate-limit",
        help="The limit of candidate tracks to search",
        min=1,
        max=20,
    ),
    playlist_size: int = typer.Option(
        10,
        "--playlist-size",
        help="Target number of tracks in the generated playlist",
        min=1,
        max=30,
    ),
    max_attempts: int = typer.Option(
        5,
        "--max-attempts",
        help="Maximum number of seed batches to process before stopping",
        min=1,
        max=10,
    ),
    max_tracks_per_artist: int = typer.Option(
        2,
        "--max-tracks-per-artist",
        help="Maximum tracks per artist in the final playlist",
        min=1,
        max=10,
    ),
    score_band_width: float = typer.Option(
        0.05,
        "--score-band-width",
        help="Width of advisor score bands for tiebreaking by reconciler confidence (0–1)",
        min=0.01,
        max=0.5,
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Discover tracks without creating a playlist"),
) -> None:
    """
    Discover new tracks similar to your library seeds.
    """
    try:
        result = asyncio.run(
            discover_similar_logic(
                email=email,
                advisor=advisor,
                provider=provider,
                config=DiscoverySimilarConfigInput(
                    seed_top=seed_top,
                    seed_saved=seed_saved,
                    seed_genres=seed_genres,
                    seed_order_by=seed_order_by,
                    seed_sort_order=seed_sort_order,
                    seed_limit=seed_limit,
                    similar_limit=similar_limit,
                    candidate_limit=candidate_limit,
                    score_band_width=score_band_width,
                    playlist_size=playlist_size,
                    max_attempts=max_attempts,
                    max_tracks_per_artist=max_tracks_per_artist,
                    dry_run=dry_run,
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
    except DiscoveryTrackNoNew as e:
        typer.secho("No new tracks found after all attempts", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    # First print the report
    table = Table(title="Discovery Report")
    table.add_column("Attempt", justify="right")
    table.add_column("Seeds", justify="right")
    table.add_column("Suggested", justify="right")
    table.add_column("Reconciled", justify="right")
    table.add_column("Survived", justify="right")
    table.add_column("New", justify="right")
    for report in result.reports:
        table.add_row(
            str(report.attempt),
            str(report.tracks_seeds),
            str(report.tracks_suggested),
            str(report.tracks_reconciled),
            str(report.tracks_survived),
            str(report.tracks_new),
        )
    console.print(table)

    # Then print the tracks discovered
    track_table = Table(title=f"Tracks added to playlist{' (dry mode)' if dry_run else ''}")
    track_table.add_column("#", justify="right", style="dim")
    track_table.add_column("Artist(s)")
    track_table.add_column("Track")
    track_table.add_column("Album", style="dim")
    for i, track in enumerate(result.tracks, start=1):
        artists = ", ".join(str(artist) for artist in track.artists)
        album_name = track.album.name if track.album else ""
        track_table.add_row(str(i), artists, track.name, album_name)
    console.print(track_table)

    # Finally, print a final message.
    if result.playlist is None:
        typer.secho(
            "\n\nTracks discovered but playlist not created (dry-run mode) \u26a0\ufe0f",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.secho(
            f"\n\nSuggested tracks successfully saved into playlist {result.playlist.name}! \u2705",
            fg=typer.colors.GREEN,
        )


async def discover_similar_logic(
    email: EmailStr,
    advisor: MusicAdvisorSimilar,
    provider: MusicProvider,
    config: DiscoverySimilarConfigInput,
) -> DiscoverySimilarResult:
    """Discovers new music for a user and creates a playlist.

    This function orchestrates the discovery process by setting up the necessary
    dependencies and executing the DiscoverSimilarUseCase.

    Args:
        email: The email of the user.
        advisor: The music advisor to use for getting recommendations.
        provider: The music provider to use for seeding and playlist creation.
        config: The configuration for the discovery process.

    Returns:
        A DiscoverySimilarResult with the playlist, per-attempt reports, and final tracks.

    Raises:
        UserNotFound: If the user with the given email is not found.
        ProviderAuthTokenNotFoundError: If the user's auth token for the provider is not found.
    """
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        auth_token_repository = get_auth_token_repository(session)
        track_repository = get_track_repository(session)

        provider_client = await stack.enter_async_context(get_provider_oauth(provider))
        provider_library_factory = get_provider_library_factory(
            provider=provider,
            session=session,
            oauth_client=provider_client,
        )

        advisor_similar = await stack.enter_async_context(get_advisor_similar_adapter(advisor))
        track_reconciler = get_track_reconciler()

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        auth_token = await auth_token_repository.get(user_id=user.id, provider=provider)
        if auth_token is None:
            raise ProviderAuthTokenNotFoundError()

        provider_library = provider_library_factory.create(user=user, auth_token=auth_token)

        use_case = DiscoverSimilarUseCase(
            track_repository=track_repository,
            provider_library=provider_library,
            advisor_client=advisor_similar,
            track_reconciler=track_reconciler,
        )

        return await use_case.create_suggestions_playlist(user=user, config=config)
