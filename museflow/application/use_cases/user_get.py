import uuid

from pydantic import EmailStr

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserNotFoundError


async def get_user(email: EmailStr, uow: UnitOfWorkPort) -> User:
    """Gets a user by email.

    Raises:
        UserNotFoundError: If no user has this email.
    """
    async with uow:
        user = await uow.users.get_by_email(email)

    if user is None:
        raise UserNotFoundError(f"User with email '{email}' not found.")

    return user


async def get_user_by_id(user_id: uuid.UUID, uow: UnitOfWorkPort) -> User:
    """Gets a user by ID, as a task message carries it.

    Raises:
        UserNotFoundError: If no user has this ID: deleted since.
    """
    async with uow:
        user = await uow.users.get_by_id(user_id)

    if user is None:
        raise UserNotFoundError(f"User {user_id} not found.")

    return user
