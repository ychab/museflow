import asyncio
from contextlib import AsyncExitStack

from pydantic import EmailStr

import typer

from museflow.application.inputs.discovery import DiscoveryConfigInput
from museflow.application.use_cases.advisor_discover import AdvisorDiscoverUseCase
from museflow.domain.entities.music import Playlist
from museflow.domain.exceptions import DiscoveryTrackNoNew
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicAdvisor
from museflow.domain.types import MusicProvider
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.infrastructure.entrypoints.cli.commands.spotify import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor_client
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_reconciler
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("discover", help="Discover new tracks for a Spotify's user account.")
def discover(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    advisor: MusicAdvisor = typer.Option(default=MusicAdvisor.LASTFM, help="The advisor to discover new musics"),
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
) -> None:
    """
    Discover new tracks for a Spotify's user account.
    """
    try:
        playlist = asyncio.run(
            discover_logic(
                email=email,
                advisor=advisor,
                config=DiscoveryConfigInput(
                    seed_top=seed_top,
                    seed_saved=seed_saved,
                    seed_genres=seed_genres,
                    seed_order_by=seed_order_by,
                    seed_sort_order=seed_sort_order,
                    seed_limit=seed_limit,
                    similar_limit=similar_limit,
                    candidate_limit=candidate_limit,
                    playlist_size=playlist_size,
                    max_attempts=max_attempts,
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

    typer.secho(
        f"\n\nSuggested tracks successfully saved into playlist {playlist.name}! \u2705",
        fg=typer.colors.GREEN,
    )


async def discover_logic(email: EmailStr, advisor: MusicAdvisor, config: DiscoveryConfigInput) -> Playlist:
    """Discovers new music for a user and creates a playlist.

    This function orchestrates the discovery process by setting up the necessary
    dependencies and executing the `AdvisorDiscoverUseCase`.

    Args:
        email: The email of the user.
        advisor: The music advisor to use for getting recommendations.
        config: The configuration for the discovery process.

    Returns:
        The newly created playlist.

    Raises:
        UserNotFound: If the user with the given email is not found.
        ProviderAuthTokenNotFoundError: If the user's auth token for Spotify is not found.
    """
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        auth_token_repository = get_auth_token_repository(session)
        track_repository = get_track_repository(session)

        spotify_client = await stack.enter_async_context(get_spotify_oauth())
        spotify_library_factory = get_spotify_library_factory(
            session=session,
            spotify_client=spotify_client,
        )

        advisor_client = await stack.enter_async_context(get_advisor_client(advisor))
        track_reconciler = get_track_reconciler()

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        auth_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        if auth_token is None:
            raise ProviderAuthTokenNotFoundError()

        spotify_library = spotify_library_factory.create(user=user, auth_token=auth_token)

        use_case = AdvisorDiscoverUseCase(
            track_repository=track_repository,
            provider_library=spotify_library,
            advisor_client=advisor_client,
            track_reconciler=track_reconciler,
        )

        return await use_case.create_suggestions_playlist(user=user, config=config)
