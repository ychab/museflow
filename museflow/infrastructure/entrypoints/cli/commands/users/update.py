import uuid

from pydantic import ValidationError

import typer

from museflow.application.inputs.user import UserUpdateInput
from museflow.application.use_cases.user_update import update_user
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.users import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.cli.parsers import parse_email
from museflow.infrastructure.entrypoints.cli.parsers import parse_password


@app.command("update", help="Update the email and/or password of a user.")
def users_update_command(
    user_id: uuid.UUID = typer.Argument(..., help="User ID to update"),
    email: str | None = typer.Option(None, help="User email address to change", parser=parse_email),
    password: str | None = typer.Option(None, help="User password to change", parser=parse_password),
) -> None:
    # Set only explicit values to update.
    attributes = {k: v for k, v in {"email": email, "password": password}.items() if v is not None}
    try:
        user_in = UserUpdateInput(**attributes)
    except ValidationError as e:
        raise typer.BadParameter(str(e)) from e

    try:
        run_logic(users_update_logic(user_id, user_in=user_in))
    except UserNotFoundError as e:
        typer.secho(f"User not found with ID {user_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"User {user_id} updated successfully!", fg=typer.colors.GREEN)


async def users_update_logic(
    user_id: uuid.UUID,
    user_in: UserUpdateInput,
) -> None:
    wiring = get_wiring()
    password_hasher = wiring.build_password_hasher()
    uow = wiring.build_unit_of_work()

    async with uow:
        user = await uow.users.get_by_id(user_id)

    if not user:
        raise UserNotFoundError()

    await update_user(
        user=user,
        user_in=user_in,
        uow=uow,
        password_hasher=password_hasher,
    )
