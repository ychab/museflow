import uuid
from typing import Any

from pydantic import EmailStr

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.inputs.user import UserCreateInput
from museflow.application.inputs.user import UserUpdateInput
from museflow.application.ports.repositories.users import UserRepository
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserAlreadyExistsError
from museflow.domain.exceptions import UserEmailAlreadyExistsError
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

    async def create(self, user_in: UserCreateInput, hashed_password: str) -> User:
        user_dict: dict[str, Any] = user_in.model_dump(exclude={"password"})
        user_dict["hashed_password"] = hashed_password

        user_db = UserModel(**user_dict)

        # The email is the only unique column: the constraint settles a race the use case's check can't see. The
        # savepoint keeps the session usable after the conflict.
        try:
            async with self.session.begin_nested():
                self.session.add(user_db)
        except IntegrityError as e:
            raise UserAlreadyExistsError("Email already registered") from e

        await self.session.refresh(user_db)

        return user_db.to_entity()

    async def update(self, user_id: uuid.UUID, user_in: UserUpdateInput, hashed_password: str | None = None) -> User:
        update_data: dict[str, Any] = user_in.model_dump(exclude_unset=True, exclude={"password"})

        if hashed_password:
            update_data["hashed_password"] = hashed_password

        stmt = update(UserModel).where(UserModel.id == user_id).values(**update_data).returning(UserModel)
        try:
            async with self.session.begin_nested():
                result = await self.session.execute(stmt)
        except IntegrityError as e:
            raise UserEmailAlreadyExistsError() from e

        user_db = result.scalar_one()

        return user_db.to_entity()

    async def delete(self, user_id: uuid.UUID) -> None:
        stmt = delete(UserModel).where(UserModel.id == user_id)

        await self.session.execute(stmt)
