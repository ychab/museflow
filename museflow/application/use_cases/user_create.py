from museflow.application.inputs.user import UserCreateInput
from museflow.application.ports.repositories.users import UserRepository
from museflow.application.ports.security import PasswordHasherPort
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserAlreadyExistsException


async def user_create(
    user_data: UserCreateInput,
    user_repository: UserRepository,
    password_hasher: PasswordHasherPort,
) -> User:
    """Creates a new user.

    This use case orchestrates the creation of a new user, including checking for
    existing users with the same email, hashing the password, and persisting the user.

    Args:
        user_data: The data for the new user.
        user_repository: The repository to store the user data.
        password_hasher: The password hasher.

    Returns:
        The newly created user.

    Raises:
        UserAlreadyExistsException: If a user with the same email already exists.
    """
    existing_user = await user_repository.get_by_email(user_data.email)
    if existing_user:
        raise UserAlreadyExistsException("Email already registered")

    hashed_password = password_hasher.hash(user_data.password)

    user = await user_repository.create(user_data, hashed_password=hashed_password)
    return user
