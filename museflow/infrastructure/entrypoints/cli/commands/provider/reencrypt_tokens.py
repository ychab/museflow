import typer

from museflow.application.use_cases.provider_token_reencrypt import reencrypt_provider_tokens
from museflow.infrastructure.entrypoints.cli.commands.provider import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic


@app.command(
    "reencrypt-tokens",
    help=(
        "Encrypt the stored tokens of every user again with the current key, the step of a key rotation before a "
        "fallback key is dropped."
    ),
)
def provider_reencrypt_tokens_command() -> None:
    try:
        reencrypted = run_logic(provider_reencrypt_tokens_logic())
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"Encrypted {reencrypted} token(s) again with the current key.", fg=typer.colors.GREEN)


async def provider_reencrypt_tokens_logic() -> int:
    return await reencrypt_provider_tokens(uow=get_wiring().build_unit_of_work())
