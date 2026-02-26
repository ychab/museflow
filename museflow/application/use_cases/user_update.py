from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserEmailAlreadyExistsException
from museflow.domain.ports.repositories.users import UserRepository
from museflow.domain.ports.security import PasswordHasherPort
from museflow.domain.schemas.user import UserUpdate


async def user_update(
    user: User,
    user_data: UserUpdate,
    user_repository: UserRepository,
    password_hasher: PasswordHasherPort,
) -> User:
    # Check if email is being changed and if it's already taken
    if user_data.email and user_data.email != user.email:
        existing = await user_repository.get_by_email(user_data.email)
        if existing:
            raise UserEmailAlreadyExistsException()

    hashed_password = password_hasher.hash(user_data.password) if user_data.password else None

    return await user_repository.update(user.id, user_data, hashed_password)
