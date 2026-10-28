from museflow.application.inputs.user import UserUpdateInput
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserEmailAlreadyExistsException


async def user_update(
    user: User,
    user_data: UserUpdateInput,
    uow: UnitOfWorkPort,
    password_hasher: PasswordHasherPort,
) -> User:
    """Updates an existing user's information.

    This use case handles updating user details, including email and password.
    It checks for email uniqueness if the email is being changed and hashes
    the new password if provided.

    Args:
        user: The `User` entity to be updated.
        user_data: The data for the user update.
        uow: The unit of work giving access to the user repository.
        password_hasher: The password hasher.

    Returns:
        The updated `User` entity.

    Raises:
        UserEmailAlreadyExistsException: If the new email is already registered by another user.
    """
    # Check if email is being changed and if it's already taken
    if user_data.email and user_data.email != user.email:
        async with uow:
            existing = await uow.users.get_by_email(user_data.email)
        if existing:
            raise UserEmailAlreadyExistsException()

    hashed_password = password_hasher.hash(user_data.password) if user_data.password else None

    async with uow:
        return await uow.users.update(user.id, user_data, hashed_password)
