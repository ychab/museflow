import uuid
from typing import Any

from pydantic import EmailStr

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserCreate
from spotifagent.domain.entities.users import UserUpdate
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.infrastructure.adapters.database.models import User as UserModel


class UserRepository(UserRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(UserModel)
            .where(UserModel.id == user_id)
            .options(  # lazy loading is not supported by async session
                selectinload(UserModel.spotify_account)
            )
        )
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        return User.model_validate(user) if user else None

    async def get_by_email(self, email: EmailStr) -> User | None:
        stmt = select(UserModel).where(UserModel.email == str(email)).options(selectinload(UserModel.spotify_account))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        return User.model_validate(user) if user else None

    async def get_by_spotify_state(self, state: str) -> User | None:
        stmt = (
            select(UserModel)
            .where(
                UserModel.spotify_state.is_not(None),
                UserModel.spotify_state == str(state),
            )
            .options(selectinload(UserModel.spotify_account))
        )
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        return User.model_validate(user) if user else None

    async def create(self, user_data: UserCreate, hashed_password: str) -> User:
        user_dict: dict[str, Any] = user_data.model_dump(exclude={"password"})
        user_dict["hashed_password"] = hashed_password

        user = UserModel(**user_dict)

        self.session.add(user)
        await self.session.commit()

        # Manually refresh to avoid lazy loading issue with async sqlalchemy
        user = await self.get_by_id(user.id)  # type: ignore[assignment]
        return User.model_validate(user)

    async def update(self, user_id: uuid.UUID, user_data: UserUpdate, hashed_password: str | None = None) -> User:
        update_data: dict[str, Any] = user_data.model_dump(exclude_unset=True, exclude={"password"})

        if hashed_password:
            update_data["hashed_password"] = hashed_password

        stmt = update(UserModel).where(UserModel.id == user_id).values(**update_data).returning(UserModel)
        result = await self.session.execute(stmt)
        user = result.scalar_one()
        await self.session.commit()

        # Manually refresh to avoid lazy loading issue with async sqlalchemy
        user = await self.get_by_id(user.id)  # type: ignore[assignment]
        return User.model_validate(user)

    async def delete(self, user_id: uuid.UUID) -> None:
        stmt = delete(UserModel).where(UserModel.id == user_id)

        await self.session.execute(stmt)
        await self.session.commit()
