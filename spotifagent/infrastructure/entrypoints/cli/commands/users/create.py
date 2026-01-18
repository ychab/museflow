from pydantic import EmailStr

import typer

from spotifagent.application.use_cases.user_create import user_create
from spotifagent.domain.entities.users import UserCreate
from spotifagent.domain.exceptions import UserAlreadyExistsException
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_db
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_password_hasher
from spotifagent.infrastructure.entrypoints.cli.dependencies import get_user_repository


async def user_create_logic(email: EmailStr, password: str) -> None:
    # First build the entity to create the user.
    user_data = UserCreate(email=email, password=password)

    password_hasher = get_password_hasher()

    # Then try to create that user in DB.
    async with get_db() as session:
        user_repository = get_user_repository(session)
        try:
            await user_create(
                user_data=user_data,
                user_repository=user_repository,
                password_hasher=password_hasher,
            )
        except UserAlreadyExistsException:
            typer.secho(f"Error: User with email {email} already exists.", fg=typer.colors.RED, err=True)
            raise
        except Exception as e:
            typer.secho(f"Unexpected error: {e}", fg=typer.colors.RED, err=True)
            raise

    typer.secho(f"User {email} created successfully!", fg=typer.colors.GREEN)
