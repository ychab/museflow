import uuid
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserCreate
from spotifagent.domain.entities.users import UserUpdate
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import PasswordHasherPort
from spotifagent.infrastructure.adapters.database.models import User as UserModel

from tests.unit.factories.users import UserCreateFactory
from tests.unit.factories.users import UserUpdateFactory


class TestUserRepository:
    @pytest.fixture
    def user_create(self) -> UserCreate:
        return UserCreateFactory.build()

    @pytest.fixture
    def user_update(self) -> UserUpdate:
        return UserUpdateFactory.build()

    async def test__get_by_id__nominal(self, user: User, user_repository: UserRepositoryPort) -> None:
        user_db = await user_repository.get_by_id(user.id)
        assert user_db is not None
        assert user_db.spotify_account is None

    async def test__get_by_id__none(self, user_repository: UserRepositoryPort) -> None:
        assert await user_repository.get_by_id(uuid.uuid4()) is None

    @pytest.mark.parametrize("user", [{"with_spotify_account": True}], indirect=["user"])
    async def test__get_by_id__with_spotify_account(self, user: User, user_repository: UserRepositoryPort) -> None:
        user_db = await user_repository.get_by_id(user.id)
        assert user_db is not None
        assert user_db.spotify_account is not None

    async def test__get_by_email__nominal(self, user: User, user_repository: UserRepositoryPort) -> None:
        user_db = await user_repository.get_by_email(user.email)
        assert user_db is not None
        assert user_db.spotify_account is None

    async def test__get_by_email__none(self, user_repository: UserRepositoryPort) -> None:
        assert await user_repository.get_by_email("foo@example.com") is None

    @pytest.mark.parametrize("user", [{"with_spotify_account": True}], indirect=["user"])
    async def test__get_by_email__with_spotify_account(self, user: User, user_repository: UserRepositoryPort) -> None:
        user_db = await user_repository.get_by_email(user.email)
        assert user_db is not None
        assert user_db.spotify_account is not None

    @pytest.mark.parametrize("user", [{"spotify_state": "dummy-token-state"}], indirect=["user"])
    async def test__get_by_spotify_state__nominal(self, user: User, user_repository: UserRepositoryPort) -> None:
        assert user.spotify_state == "dummy-token-state"

        user_db = await user_repository.get_by_spotify_state(user.spotify_state)
        assert user_db is not None
        assert user_db.id == user.id
        assert user_db.spotify_account is None

    async def test__get_by_spotify_state__none(self, user_repository: UserRepositoryPort) -> None:
        assert await user_repository.get_by_spotify_state("dummy-token-state") is None

    @pytest.mark.parametrize(
        "user",
        [{"spotify_state": "dummy-token-state", "with_spotify_account": True}],
        indirect=["user"],
    )
    async def test__get_by_spotify_state__with_spotify_account(
        self,
        user: User,
        user_repository: UserRepositoryPort,
    ) -> None:
        assert user.spotify_state == "dummy-token-state"

        user_db = await user_repository.get_by_spotify_state(user.spotify_state)
        assert user_db is not None
        assert user_db.id == user.id
        assert user_db.spotify_account is not None

    async def test__create__nominal(
        self,
        user_create: UserCreate,
        user_repository: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        hashed_password = password_hasher.hash(user_create.password)

        user = await user_repository.create(user_create, hashed_password=hashed_password)

        assert user.id
        assert user.email == user_create.email
        assert password_hasher.verify(user_create.password, user.hashed_password)
        assert user.is_active is True
        assert user.created_at.tzinfo == UTC
        assert user.updated_at.tzinfo == UTC

    async def test__update__all(
        self,
        user: User,
        user_update: UserUpdate,
        user_repository: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        assert user_update.email is not None and user_update.password is not None
        hashed_password = password_hasher.hash(user_update.password)

        assert user_update.email != user.email
        assert hashed_password != user.hashed_password

        user_updated = await user_repository.update(user.id, user_update, hashed_password)

        assert user_updated.email == user_update.email
        assert password_hasher.verify(user_update.password, user_updated.hashed_password)
        assert user_updated.is_active is True

        assert user_updated.spotify_state is not None
        assert user_updated.created_at == user.created_at
        assert user_updated.updated_at >= user.updated_at

    async def test__update__no_password(
        self,
        user: User,
        user_update: UserUpdate,
        user_repository: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
    ) -> None:
        assert user_update.email is not None and user_update.email != user.email

        # Trick to unset the password field automatically generated by Polyfactory.
        user_update.password = None
        user_update.model_fields_set.discard("password")

        user_updated = await user_repository.update(user.id, user_update)
        assert user_updated.email == user_update.email
        assert password_hasher.verify("testtest", user_updated.hashed_password)
        assert user_updated.updated_at >= user.updated_at

    async def test__delete__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
        user_repository: UserRepositoryPort,
    ) -> None:
        await user_repository.delete(user.id)

        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar_one_or_none() is None
