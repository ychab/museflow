import logging

from pydantic import EmailStr

from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserInactive
from museflow.domain.exceptions import UserInvalidCredentials
from museflow.domain.exceptions import UserNotFound
from museflow.domain.ports.repositories.users import UserRepository
from museflow.domain.ports.security import PasswordHasherPort

logger = logging.getLogger(__name__)


async def user_authenticate(
    email: EmailStr,
    password: str,
    user_repository: UserRepository,
    password_hasher: PasswordHasherPort,
) -> User:
    """Authenticates a user based on their email and password.

    This use case retrieves a user by email, verifies their password, and checks
    if the user account is active.

    Args:
        email: The user's email address.
        password: The user's plain text password.
        user_repository: The repository for user data.
        password_hasher: The password hasher.

    Returns:
        The authenticated `User` entity.

    Raises:
        UserNotFound: If no user with the given email exists.
        UserInvalidCredentials: If the provided password does not match.
        UserInactive: If the user account is not active.
    """
    user = await user_repository.get_by_email(email)

    if not user:
        raise UserNotFound()

    if not password_hasher.verify(password, user.hashed_password):
        raise UserInvalidCredentials()

    if not user.is_active:
        raise UserInactive()

    return user
