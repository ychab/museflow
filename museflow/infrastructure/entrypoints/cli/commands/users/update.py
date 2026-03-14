import asyncio
import uuid

from pydantic import ValidationError

import typer

from museflow.application.inputs.user import UserUpdateInput
from museflow.application.use_cases.user_update import user_update
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.users import app
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_password_hasher
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email
from museflow.infrastructure.entrypoints.cli.parsers import parse_password


@app.command("update")
def update(
    user_id: uuid.UUID = typer.Argument(..., help="User ID to update"),
    email: str | None = typer.Option(None, help="User email address to change", parser=parse_email),
    password: str | None = typer.Option(None, help="User password to change", parser=parse_password),
) -> None:
    # Set only explicit values to update.
    attributes = {k: v for k, v in {"email": email, "password": password}.items() if v is not None}
    try:
        user_data = UserUpdateInput(**attributes)
    except ValidationError as e:
        raise typer.BadParameter(str(e)) from e

    try:
        asyncio.run(user_update_logic(user_id, user_data=user_data))
    except UserNotFound as e:
        typer.secho(f"User not found with ID {user_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    typer.secho(f"User {user_id} updated successfully!", fg=typer.colors.GREEN)


async def user_update_logic(
    user_id: uuid.UUID,
    user_data: UserUpdateInput,
) -> None:
    password_hasher = get_password_hasher()

    async with get_db() as session:
        user_repository = get_user_repository(session)

        user = await user_repository.get_by_id(user_id)
        if not user:
            raise UserNotFound()

        await user_update(
            user=user,
            user_data=user_data,
            user_repository=user_repository,
            password_hasher=password_hasher,
        )
