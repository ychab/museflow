import asyncio

from pydantic import EmailStr

import typer

from museflow.application.inputs.user import UserCreateInput
from museflow.application.use_cases.user_create import user_create
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserAlreadyExistsException
from museflow.infrastructure.entrypoints.cli.commands.users import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_password_hasher
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.parsers import parse_email
from museflow.infrastructure.entrypoints.cli.parsers import parse_password


@app.command("create", help="Create a new user account.")
def create(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    password: str = typer.Option(
        None,
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="User password (prompted if omitted)",
        parser=parse_password,
    ),
) -> None:
    try:
        asyncio.run(user_create_logic(email, password))
    except UserAlreadyExistsException as e:
        typer.secho(f"User with email {email} already exists.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"User {email} created successfully!", fg=typer.colors.GREEN)


async def user_create_logic(email: EmailStr, password: str) -> User:
    password_hasher = get_password_hasher()

    return await user_create(
        user_data=UserCreateInput(email=email, password=password),
        uow=get_unit_of_work(),
        password_hasher=password_hasher,
    )
