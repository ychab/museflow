import uuid
from typing import Any

from pydantic import EmailStr

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.user import User
from museflow.domain.ports.repositories.users import UserRepository
from museflow.domain.schemas.user import UserCreate
from museflow.domain.schemas.user import UserUpdate
from museflow.infrastructure.adapters.database.models import User as UserModel


class UserSQLRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        user_db = result.scalar_one_or_none()

        return user_db.to_entity() if user_db else None

    async def get_by_email(self, email: EmailStr) -> User | None:
        stmt = select(UserModel).where(UserModel.email == str(email))
        result = await self.session.execute(stmt)
        user_db = result.scalar_one_or_none()

        return user_db.to_entity() if user_db else None

    async def create(self, user_data: UserCreate, hashed_password: str) -> User:
        user_dict: dict[str, Any] = user_data.model_dump(exclude={"password"})
        user_dict["hashed_password"] = hashed_password

        user_db = UserModel(**user_dict)

        self.session.add(user_db)
        await self.session.commit()
        await self.session.refresh(user_db)

        return user_db.to_entity()

    async def update(self, user_id: uuid.UUID, user_data: UserUpdate, hashed_password: str | None = None) -> User:
        update_data: dict[str, Any] = user_data.model_dump(exclude_unset=True, exclude={"password"})

        if hashed_password:
            update_data["hashed_password"] = hashed_password

        stmt = update(UserModel).where(UserModel.id == user_id).values(**update_data).returning(UserModel)
        result = await self.session.execute(stmt)
        user_db = result.scalar_one()

        await self.session.commit()
        await self.session.refresh(user_db)

        return user_db.to_entity()

    async def delete(self, user_id: uuid.UUID) -> None:
        stmt = delete(UserModel).where(UserModel.id == user_id)

        await self.session.execute(stmt)
        await self.session.commit()
