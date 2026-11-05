import asyncio
import time
import uuid
from dataclasses import dataclass

from pydantic import EmailStr

import typer
from rich import get_console

from museflow.application.use_cases.provider_oauth_redirect import oauth_redirect
from museflow.application.use_cases.provider_token_view import view_provider_token
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.provider import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_provider_oauth
from museflow.infrastructure.entrypoints.cli.dependencies import get_state_token_generator
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


@dataclass(frozen=True, kw_only=True)
class ConnectStart:
    user_id: uuid.UUID
    provider: MusicProvider
    previous_token: OAuthProviderUserToken | None
    authorization_url: str


@app.command("connect", help="Connect a user account to a music provider via OAuth.")
def connect(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    provider: MusicProvider = typer.Option(MusicProvider.SPOTIFY, "--provider", help="Music provider to connect"),
    timeout: float = typer.Option(60.0, help="Seconds to wait for authentication.", min=10),
    poll_interval: float = typer.Option(2.0, help="Seconds between status checks.", min=0.5),
) -> None:
    """
    Initiates the provider's OAuth flow for a specific user.

    Important: the app must be run and being able to receive the provider's callback
    define with the provider's redirect URI setting (e.g. SPOTIFY_REDIRECT_URI).
    """
    try:
        # One event loop for both steps: the pooled database connections are bound to it.
        with asyncio.Runner() as runner:
            start = runner.run(connect_start_logic(email, provider))

            typer.echo(f"Opening browser for authentication: {start.authorization_url}")
            typer.launch(start.authorization_url)

            with get_console().status("Waiting for authentication completion..."):
                runner.run(connect_wait_logic(start, timeout, poll_interval))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TimeoutError as e:
        typer.secho(
            f"Unable to connect after {timeout} seconds. Did you open your browser and accept?",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho("Authentication successful! \u2705", fg=typer.colors.GREEN)


async def connect_start_logic(email: EmailStr, provider: MusicProvider) -> ConnectStart:
    uow = get_unit_of_work()
    async with uow:
        user = await uow.users.get_by_email(email)
    if not user:
        raise UserNotFound()

    previous_token = await view_provider_token(user_id=user.id, provider=provider, uow=uow)

    async with get_provider_oauth(provider) as provider_oauth:
        authorization_url = await oauth_redirect(
            user=user,
            uow=uow,
            provider=provider,
            provider_oauth=provider_oauth,
            state_token_generator=get_state_token_generator(),
        )

    return ConnectStart(
        user_id=user.id,
        provider=provider,
        previous_token=previous_token,
        authorization_url=authorization_url,
    )


async def connect_wait_logic(start: ConnectStart, timeout: float, poll_interval: float) -> None:
    uow = get_unit_of_work()
    start_time = time.time()

    while time.time() - start_time < timeout:
        await asyncio.sleep(poll_interval)

        # Only a new token proves success: the API callback consumes the state even when the flow then fails.
        token = await view_provider_token(user_id=start.user_id, provider=start.provider, uow=uow)
        if token != start.previous_token:
            return

    raise TimeoutError()
