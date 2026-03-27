import asyncio
import time
import uuid
from contextlib import AsyncExitStack

from pydantic import EmailStr

from sqlalchemy.ext.asyncio import AsyncSession

import typer

from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.use_cases.provider_oauth_redirect import oauth_redirect
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.spotify import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_auth_state_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_spotify_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_state_token_generator
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@app.command("connect", help="Connect a user account to Spotify via OAuth.")
def connect(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    timeout: float = typer.Option(60.0, help="Seconds to wait for authentication.", min=10),
    poll_interval: float = typer.Option(2.0, help="Seconds between status checks.", min=0.5),
) -> None:
    """
    Initiates the Spotify OAuth flow for a specific user.

    Important: the app must be run and being able to receive the Spotify's callback
    define with the setting SPOTIFY_REDIRECT_URI.
    """
    try:
        asyncio.run(connect_logic(email, timeout, poll_interval))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TimeoutError as e:
        typer.secho(
            f"\n\nUnable to connect after {timeout} seconds. Did you open your browser and accept?",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho("\n\nAuthentication successful! \u2705", fg=typer.colors.GREEN)


async def connect_logic(email: EmailStr, timeout: float, poll_interval: float) -> None:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())
        provider_oauth = await stack.enter_async_context(get_spotify_oauth())
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
            provider_oauth=provider_oauth,
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
    auth_state_repository: OAuthProviderStateRepository,
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
