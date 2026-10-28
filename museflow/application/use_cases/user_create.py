from museflow.application.inputs.user import UserCreateInput
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserAlreadyExistsException


async def user_create(
    user_data: UserCreateInput,
    uow: UnitOfWorkPort,
    password_hasher: PasswordHasherPort,
) -> User:
    """Creates a new user.

    This use case orchestrates the creation of a new user, including checking for
    existing users with the same email, hashing the password, and persisting the user.

    Args:
        user_data: The data for the new user.
        uow: The unit of work giving access to the user repository.
        password_hasher: The password hasher.

    Returns:
        The newly created user.

    Raises:
        UserAlreadyExistsException: If a user with the same email already exists.
    """
    async with uow:
        existing_user = await uow.users.get_by_email(user_data.email)
    if existing_user:
        raise UserAlreadyExistsException("Email already registered")

    # Hashing is slow on purpose: keep it out of the block.
    hashed_password = password_hasher.hash(user_data.password)

    async with uow:
        return await uow.users.create(user_data, hashed_password=hashed_password)
