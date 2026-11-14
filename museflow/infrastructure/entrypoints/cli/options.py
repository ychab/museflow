from typing import Final

import typer

from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


def resolve_email(value: str | None) -> str:
    email = value or app_settings.CLI_DEFAULT_EMAIL
    if not email:
        raise typer.BadParameter("required, pass it or set MUSEFLOW_CLI_DEFAULT_EMAIL")

    return email


# The setting is validated on load: only the option needs the parser.
EMAIL_OPTION: Final[str] = typer.Option(
    None,
    help="User email address [default: MUSEFLOW_CLI_DEFAULT_EMAIL]",
    parser=parse_email,
    callback=resolve_email,
)
