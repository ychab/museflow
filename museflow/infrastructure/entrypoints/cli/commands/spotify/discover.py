from contextlib import AsyncExitStack

from pydantic import EmailStr

from museflow.application.use_cases.advisor_discover import AdvisorDiscoverUseCase
from museflow.application.use_cases.advisor_discover import DiscoveryConfig
from museflow.domain.entities.music import Playlist
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicAdvisor
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor_client
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_client
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_reconciler
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository


async def discover_logic(email: EmailStr, advisor: MusicAdvisor, config: DiscoveryConfig) -> Playlist:
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

        spotify_client = await stack.enter_async_context(get_spotify_client())
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
