import logging

from pydantic import EmailStr

from museflow.domain.entities.users import User
from museflow.domain.exceptions import UserInactive
from museflow.domain.exceptions import UserInvalidCredentials
from museflow.domain.exceptions import UserNotFound
from museflow.domain.ports.repositories.users import UserRepositoryPort
from museflow.domain.ports.security import PasswordHasherPort

logger = logging.getLogger(__name__)


async def user_authenticate(
    email: EmailStr,
    password: str,
    user_repository: UserRepositoryPort,
    password_hasher: PasswordHasherPort,
) -> User:
    user = await user_repository.get_by_email(email)

    if not user:
        raise UserNotFound()

    if not password_hasher.verify(password, user.hashed_password):
        raise UserInvalidCredentials()

    if not user.is_active:
        raise UserInactive()

    return user
