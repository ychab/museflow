import uuid
from abc import ABC
from abc import abstractmethod

from pydantic import EmailStr

from museflow.domain.entities.user import User
from museflow.domain.schemas.user import UserCreate
from museflow.domain.schemas.user import UserUpdate


class UserRepository(ABC):
    """A repository for managing `User` entities.

    This repository provides a comprehensive interface for all CRUD (Create, Read,
    Update, Delete) operations related to users.
    """

    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Retrieves a user by their unique ID.

        Args:
            user_id: The UUID of the user to retrieve.

        Returns:
            The `User` entity if found, otherwise None.
        """
        ...

    @abstractmethod
    async def get_by_email(self, email: EmailStr) -> User | None:
        """Retrieves a user by their unique email address.

        Args:
            email: The email address of the user to retrieve.

        Returns:
            The `User` entity if found, otherwise None.
        """
        ...

    @abstractmethod
    async def create(self, user_data: UserCreate, hashed_password: str) -> User:
        """Creates a new user in the database.

        Args:
            user_data: A schema object containing the user's details (e.g., email).
            hashed_password: The user's password, already hashed.

        Returns:
            The newly created `User` entity.
        """
        ...

    @abstractmethod
    async def update(self, user_id: uuid.UUID, user_data: UserUpdate, hashed_password: str | None = None) -> User:
        """Updates an existing user's information.

        Args:
            user_id: The ID of the user to update.
            user_data: A schema object with the fields to be updated.
            hashed_password: An optional new hashed password if the password is being changed.

        Returns:
            The updated `User` entity.
        """
        ...

    @abstractmethod
    async def delete(self, user_id: uuid.UUID) -> None:
        """Deletes a user from the database.

        Args:
            user_id: The ID of the user to delete.
        """
        ...
