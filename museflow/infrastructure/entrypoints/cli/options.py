import typer

from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


def resolve_email(value: str | None) -> str:
    email = value if value is not None else app_settings.CLI_DEFAULT_EMAIL
    if not email:
        raise typer.BadParameter("required, pass it or set MUSEFLOW_CLI_DEFAULT_EMAIL")

    return parse_email(email)


EMAIL_OPTION: str = typer.Option(
    None, help="User email address [default: MUSEFLOW_CLI_DEFAULT_EMAIL]", callback=resolve_email
)
