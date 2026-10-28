import logging

from pydantic import EmailStr

from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserInactive
from museflow.domain.exceptions import UserInvalidCredentials
from museflow.domain.exceptions import UserNotFound

logger = logging.getLogger(__name__)


async def user_authenticate(
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
        UserNotFound: If no user with the given email exists.
        UserInvalidCredentials: If the provided password does not match.
        UserInactive: If the user account is not active.
    """
    async with uow:
        user = await uow.users.get_by_email(email)

    if not user:
        raise UserNotFound()

    if not password_hasher.verify(password, user.hashed_password):
        raise UserInvalidCredentials()

    if not user.is_active:
        raise UserInactive()

    return user
