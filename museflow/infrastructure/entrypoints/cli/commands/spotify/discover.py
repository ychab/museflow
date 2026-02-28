from contextlib import AsyncExitStack

from pydantic import EmailStr

from museflow.application.use_cases.advisor_discovery_tracks import discover_tracks
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicAdvisor
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.dependencies import get_advisor_client
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_client
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository


async def discover_logic(email: EmailStr, advisor: MusicAdvisor) -> None:
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

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        auth_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        if auth_token is None:
            raise ProviderAuthTokenNotFoundError()

        spotify_library = spotify_library_factory.create(user=user, auth_token=auth_token)

        tracks_suggested = await discover_tracks(
            user=user,
            track_repository=track_repository,
            provider_library=spotify_library,
            advisor_client=advisor_client,
        )
        print(f"Suggested tracks for user {user.email}:\n{tracks_suggested}")

    return None
