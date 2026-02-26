import uuid

from museflow.application.use_cases.user_update import user_update
from museflow.domain.exceptions import UserNotFound
from museflow.domain.schemas.user import UserUpdate
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_password_hasher
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository


async def user_update_logic(
    user_id: uuid.UUID,
    user_data: UserUpdate,
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
