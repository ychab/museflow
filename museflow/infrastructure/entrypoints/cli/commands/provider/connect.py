from dataclasses import dataclass
from urllib.parse import parse_qs
from urllib.parse import urlsplit

from pydantic import EmailStr

import typer

from museflow.application.use_cases.provider_oauth_code_exchange import exchange_oauth_code
from museflow.application.use_cases.provider_oauth_redirect_url_build import build_oauth_redirect_url
from museflow.application.use_cases.provider_oauth_state_consume import consume_oauth_state
from museflow.application.use_cases.user_get import get_user
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderExchangeCodeError
from museflow.domain.exceptions import ProviderOAuthAuthorizationError
from museflow.domain.exceptions import ProviderOAuthStateInvalidError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.commands.provider import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import init_logic_runner
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION


@dataclass(frozen=True, kw_only=True)
class ConnectStart:
    user: User
    provider: MusicProvider
    authorization_url: str


@app.command("connect", help="Connect a user account to a music provider via OAuth.")
def provider_connect_command(
    email: str = EMAIL_OPTION,
    provider: MusicProvider = typer.Option(MusicProvider.SPOTIFY, "--provider", help="Music provider to connect"),
) -> None:
    """
    Initiates the provider's OAuth flow for a specific user.

    The provider sends the browser back to a loopback address where nothing listens: the user pastes the URL of that
    page, so the code never leaves the machine running the command.
    """
    try:
        # One event loop for both steps: the pooled database connections are bound to it.
        with init_logic_runner() as runner:
            start = runner.run(provider_connect_start_logic(email, provider))

            typer.echo(f"Opening browser for authentication: {start.authorization_url}")
            typer.launch(start.authorization_url)

            redirect_url = typer.prompt(
                f"Once you have accepted, the browser lands on {app_settings.cli_oauth_redirect_uri}, which does not "
                "load: paste the full URL of that page"
            )
            runner.run(provider_connect_complete_logic(start, redirect_url))
    except UserNotFoundError as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except ProviderOAuthStateInvalidError as e:
        typer.secho(
            "The URL holds an unknown or expired state: run the command again.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except ProviderOAuthAuthorizationError as e:
        typer.secho(f"The provider refused the authorisation: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except ProviderExchangeCodeError as e:
        typer.secho(
            f"Unable to exchange the authorisation code with the provider: {e.__cause__}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho("Authentication successful! ✅", fg=typer.colors.GREEN)


async def provider_connect_start_logic(email: EmailStr, provider: MusicProvider) -> ConnectStart:
    wiring = get_wiring()
    uow = wiring.build_unit_of_work()
    user = await get_user(email=email, uow=uow)

    async with wiring.build_provider_oauth(provider, app_settings.cli_oauth_redirect_uri) as provider_oauth:
        authorization_url = await build_oauth_redirect_url(
            user=user,
            uow=uow,
            provider=provider,
            provider_oauth=provider_oauth,
            state_token_generator=wiring.build_state_token_generator(),
        )

    return ConnectStart(user=user, provider=provider, authorization_url=authorization_url)


async def provider_connect_complete_logic(start: ConnectStart, redirect_url: str) -> None:
    redirect_uri = app_settings.cli_oauth_redirect_uri
    url = urlsplit(redirect_url.strip())

    # Checked before the state is consumed: a wrong paste (the authorisation URL, which holds the state too) must not
    # spend it.
    if f"{url.scheme}://{url.netloc}{url.path}" != str(redirect_uri):
        raise ValueError(f"Not the URL of the redirect: it starts with {redirect_uri}")

    params = {key: values[0] for key, values in parse_qs(url.query).items()}
    wiring = get_wiring()
    uow = wiring.build_unit_of_work()

    # Single use, even when the consent was refused: a new flow needs a new command.
    await consume_oauth_state(state=params.get("state", ""), user=start.user, provider=start.provider, uow=uow)

    if "error" in params or "code" not in params:
        raise ProviderOAuthAuthorizationError(params.get("error", "no authorisation code received"))

    async with wiring.build_provider_oauth(start.provider, redirect_uri) as provider_oauth:
        await exchange_oauth_code(
            code=params["code"],
            user=start.user,
            provider=start.provider,
            uow=uow,
            provider_oauth=provider_oauth,
        )
