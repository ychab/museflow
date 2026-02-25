from museflow.domain.entities.users import User
from museflow.domain.entities.users import UserCreate
from museflow.domain.exceptions import UserAlreadyExistsException
from museflow.domain.ports.repositories.users import UserRepositoryPort
from museflow.domain.ports.security import PasswordHasherPort


async def user_create(
    user_data: UserCreate,
    user_repository: UserRepositoryPort,
    password_hasher: PasswordHasherPort,
) -> User:
    existing_user = await user_repository.get_by_email(user_data.email)
    if existing_user:
        raise UserAlreadyExistsException("Email already registered")

    hashed_password = password_hasher.hash(user_data.password)

    user = await user_repository.create(user_data, hashed_password=hashed_password)
    return user
