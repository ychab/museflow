import uuid

from pydantic import EmailStr

import typer

from spotifagent.application.use_cases.user_update import user_update
from spotifagent.domain.entities.users import UserUpdate
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_db
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_password_hasher
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_user_repository


async def user_update_logic(
    user_id: uuid.UUID,
    email: EmailStr | None = None,
    password: str | None = None,
) -> None:
    field_values = {"email": email, "password": password}
    attributes = {k: v for k, v in field_values.items() if v is not None}
    if not attributes:
        raise typer.BadParameter("At least one field to update must be provided.")

    user_data = UserUpdate(**attributes)

    password_hasher = get_password_hasher()

    # Then try to create that user in DB.
    async with get_db() as session:
        user_repository = get_user_repository(session)

        user = await user_repository.get_by_id(user_id)
        if not user:
            raise typer.BadParameter(f"User not found with ID {user_id}")

        try:
            await user_update(
                user=user,
                user_data=user_data,
                user_repository=user_repository,
                password_hasher=password_hasher,
            )
        except Exception as e:
            typer.secho(f"Unexpected error: {e}", fg=typer.colors.RED, err=True)
            raise

    typer.secho(f"User {email} updated successfully!", fg=typer.colors.GREEN)
