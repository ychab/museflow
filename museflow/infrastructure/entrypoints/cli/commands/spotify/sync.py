from contextlib import AsyncExitStack

from pydantic import EmailStr

from museflow.application.use_cases.provider_sync_library import ProviderSyncLibraryUseCase
from museflow.application.use_cases.provider_sync_library import SyncConfig
from museflow.application.use_cases.provider_sync_library import SyncReport
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.dependencies import get_artist_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_token_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_client
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_library_factory
from museflow.infrastructure.entrypoints.cli.dependencies import get_track_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository


async def sync_logic(email: EmailStr, config: SyncConfig) -> SyncReport:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        spotify_client = await stack.enter_async_context(get_spotify_client())
        spotify_library_factory = get_spotify_library_factory(
            session=session,
            spotify_client=spotify_client,
        )

        user_repository = get_user_repository(session)
        auth_token_repository = get_auth_token_repository(session)
        artist_repository = get_artist_repository(session)
        track_repository = get_track_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        auth_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)
        if auth_token is None:
            raise ProviderAuthTokenNotFoundError()

        spotify_library = spotify_library_factory.create(user=user, auth_token=auth_token)

        use_case = ProviderSyncLibraryUseCase(
            provider_library=spotify_library,
            artist_repository=artist_repository,
            track_repository=track_repository,
        )
        return await use_case.execute(
            user=user,
            config=config,
        )
