import logging

from pydantic import EmailStr

from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserInactiveError
from museflow.domain.exceptions import UserInvalidCredentialsError
from museflow.domain.exceptions import UserNotFoundError

logger = logging.getLogger(__name__)


async def authenticate_user(
    email: EmailStr,
    password: str,
    uow: UnitOfWorkPort,
    password_hasher: PasswordHasherPort,
) -> User:
    """Authenticates a user based on their email and password.

    This use case retrieves a user by email, verifies their password, and checks
    if the user account is active.

    Args:
        email: The user's email address.
        password: The user's plain text password.
        uow: The unit of work giving access to the user repository.
        password_hasher: The password hasher.

    Returns:
        The authenticated `User` entity.

    Raises:
        UserNotFoundError: If no user with the given email exists.
        UserInvalidCredentialsError: If the provided password does not match.
        UserInactiveError: If the user account is not active.
    """
    async with uow:
        user = await uow.users.get_by_email(email)

    if not user:
        password_hasher.verify_simulate(password)
        raise UserNotFoundError()

    if not password_hasher.verify(password, user.hashed_password):
        raise UserInvalidCredentialsError()

    if not user.is_active:
        raise UserInactiveError()

    return user
