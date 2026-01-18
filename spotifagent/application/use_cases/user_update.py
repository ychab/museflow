from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserUpdate
from spotifagent.domain.exceptions import EmailAlreadyExistsException
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import PasswordHasherPort


async def user_update(
    user: User,
    user_data: UserUpdate,
    user_repository: UserRepositoryPort,
    password_hasher: PasswordHasherPort,
) -> User:
    # Check if email is being changed and if it's already taken
    if user_data.email and user_data.email != user.email:
        existing = await user_repository.get_by_email(user_data.email)
        if existing:
            raise EmailAlreadyExistsException()

    hashed_password = password_hasher.hash(user_data.password) if user_data.password else None

    return await user_repository.update(user.id, user_data, hashed_password)
