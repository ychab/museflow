import uuid
from abc import ABC
from abc import abstractmethod

from pydantic import EmailStr

from museflow.domain.entities.users import User
from museflow.domain.entities.users import UserCreate
from museflow.domain.entities.users import UserUpdate


class UserRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: EmailStr) -> User | None: ...

    @abstractmethod
    async def create(self, user_data: UserCreate, hashed_password: str) -> User: ...

    @abstractmethod
    async def update(self, user_id: uuid.UUID, user_data: UserUpdate, hashed_password: str | None = None) -> User: ...

    @abstractmethod
    async def delete(self, user_id: uuid.UUID) -> None: ...
