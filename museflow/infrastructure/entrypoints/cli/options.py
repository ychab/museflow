from typing import Annotated

import typer

from museflow.infrastructure.config.settings.app import app_settings
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


def resolve_email(value: str | None) -> str:
    email = value or app_settings.CLI_DEFAULT_EMAIL
    if not email:
        raise typer.BadParameter("required, pass it or set MUSEFLOW_CLI_DEFAULT_EMAIL")

    return email


# The setting is validated on load: only the option needs the parser. No default of its own: the callback falls back on
# the setting, so the parameter stays a required `str` for a direct call.
EmailOption = Annotated[
    str,
    typer.Option(
        help="User email address [default: MUSEFLOW_CLI_DEFAULT_EMAIL]",
        parser=parse_email,
        callback=resolve_email,
        default_factory=lambda: None,
        show_default=False,
    ),
]

VerboseOption = Annotated[
    bool,
    typer.Option(
        "--verbose",
        help="Show the details of the run: the LLM usage per step and model, and the steps of each attempt if any.",
    ),
]
