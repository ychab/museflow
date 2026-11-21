from typing import Annotated

from pydantic import EmailStr

import typer

from museflow.application.inputs.user import UserCreateInput
from museflow.application.use_cases.user_create import create_user
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserAlreadyExistsError
from museflow.infrastructure.entrypoints.cli.commands.users import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.parsers import parse_email
from museflow.infrastructure.entrypoints.cli.parsers import parse_password


@app.command("create", help="Create a new user account.")
def users_create_command(
    email: Annotated[str, typer.Option(help="User email address", parser=parse_email)],
    password: Annotated[
        str,
        typer.Option(
            prompt=True,
            hide_input=True,
            confirmation_prompt=True,
            help="User password (prompted if omitted)",
            parser=parse_password,
            # No default of its own: the prompt asks for it, so the parameter stays a required `str` for a direct call.
            default_factory=lambda: None,
            show_default=False,
        ),
    ],
) -> None:
    try:
        run_logic(users_create_logic(email, password))
    except UserAlreadyExistsError as e:
        typer.secho(f"User with email {email} already exists.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"User {email} created successfully!", fg=typer.colors.GREEN)


async def users_create_logic(email: EmailStr, password: str) -> User:
    wiring = get_wiring()
    password_hasher = wiring.build_password_hasher()

    return await create_user(
        user_in=UserCreateInput(email=email, password=password),
        uow=wiring.build_unit_of_work(),
        password_hasher=password_hasher,
    )
