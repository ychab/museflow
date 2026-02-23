import logging

from pydantic import EmailStr

from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import UserInactive
from spotifagent.domain.exceptions import UserInvalidCredentials
from spotifagent.domain.exceptions import UserNotFound
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import PasswordHasherPort

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
