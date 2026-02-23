import asyncio
import time
import uuid
from contextlib import AsyncExitStack

from pydantic import EmailStr

from sqlalchemy.ext.asyncio import AsyncSession

import typer

from spotifagent.application.use_cases.provider_oauth_redirect import oauth_redirect
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.exceptions import UserNotFound
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_auth_state_repository
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_db
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_spotify_client
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_state_token_generator
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_user_repository


async def connect_logic(email: EmailStr, timeout: float, poll_interval: float) -> None:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        provider_client = await stack.enter_async_context(get_spotify_client())
        user_repository = get_user_repository(session)
        auth_state_repository = get_auth_state_repository(session)
        state_token_generator = get_state_token_generator()

        user = await user_repository.get_by_email(email)
        if not user:
            raise UserNotFound()

        authorization_url = await oauth_redirect(
            user=user,
            auth_state_repository=auth_state_repository,
            provider=MusicProvider.SPOTIFY,
            provider_client=provider_client,
            state_token_generator=state_token_generator,
        )

        # Then launch a browser.
        typer.echo(f"Opening browser for authentication: {authorization_url}")
        typer.launch(str(authorization_url))

        await _wait_for_authentication(
            session=session,
            auth_state_repository=auth_state_repository,
            user_id=user.id,
            timeout=timeout,
            poll_interval=poll_interval,
        )


async def _wait_for_authentication(
    session: AsyncSession,
    auth_state_repository: OAuthProviderStateRepositoryPort,
    user_id: uuid.UUID,
    timeout: float,
    poll_interval: float,
) -> None:
    typer.echo("Waiting for authentication completion", nl=False)
    start_time = time.time()

    while time.time() - start_time < timeout:
        await asyncio.sleep(poll_interval)
        typer.echo(".", nl=False)  # Visual feedback

        # Force SQLAlchemy to forget cached data so we see external updates
        session.expire_all()

        auth_state = await auth_state_repository.get(user_id=user_id, provider=MusicProvider.SPOTIFY)
        if auth_state is None:
            return

    raise TimeoutError()
