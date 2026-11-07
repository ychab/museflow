import asyncio
from dataclasses import asdict
from dataclasses import replace

from pydantic import EmailStr

import typer
from rich.pretty import Pretty

from museflow.application.use_cases.provider_token_view import get_provider_token
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.provider import app
from museflow.infrastructure.entrypoints.cli.commands.provider import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.options import EMAIL_OPTION


def _mask(secret: str) -> str:
    # The last characters tell two tokens apart, e.g. after a rotation
    return f"****{secret[-4:]}"


@app.command("info", help="Show the stored provider auth token of a user.")
def info(
    email: str = EMAIL_OPTION,
    provider: MusicProvider = typer.Option(MusicProvider.SPOTIFY, "--provider", help="Music provider of the token"),
    show_tokens: bool = typer.Option(False, "--show-tokens", help="Print the tokens in clear, after a confirmation"),
) -> None:
    if show_tokens:
        typer.confirm("This prints the tokens in clear. Continue?", abort=True)

    try:
        token = asyncio.run(info_logic(email=email, provider=provider))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if token:
        if not show_tokens:
            token = replace(token, token_access=_mask(token.token_access), token_refresh=_mask(token.token_refresh))
        console.print(f"{provider.title()} Auth Token:")
        console.print(Pretty(asdict(token)), soft_wrap=True)


async def info_logic(email: EmailStr, provider: MusicProvider) -> OAuthProviderUserToken | None:
    uow = get_unit_of_work()

    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFound(f"User with email '{email}' not found.")

    return await get_provider_token(user_id=user.id, provider=provider, uow=uow)
