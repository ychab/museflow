from pydantic import EmailStr

from museflow.application.use_cases.user_create import user_create
from museflow.domain.entities.users import User
from museflow.domain.entities.users import UserCreate
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_password_hasher
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository


async def user_create_logic(email: EmailStr, password: str) -> User:
    password_hasher = get_password_hasher()

    async with get_db() as session:
        user = await user_create(
            user_data=UserCreate(email=email, password=password),
            user_repository=get_user_repository(session),
            password_hasher=password_hasher,
        )

    return user
