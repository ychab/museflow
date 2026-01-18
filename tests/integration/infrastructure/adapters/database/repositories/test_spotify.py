import uuid
from datetime import UTC
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from spotifagent.domain.entities.spotify import SpotifyAccount
from spotifagent.domain.entities.spotify import SpotifyAccountCreate
from spotifagent.domain.entities.spotify import SpotifyAccountUpdate
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.spotify import SpotifyAccountRepositoryPort
from spotifagent.infrastructure.adapters.database.models import SpotifyAccount as SpotifyAccountModel

from tests.unit.factories.spotify import SpotifyAccountCreateFactory
from tests.unit.factories.spotify import SpotifyAccountUpdateFactory


class TestSpotifyAccountRepository:
    @pytest.fixture
    def spotify_account_create(self) -> SpotifyAccountCreate:
        return SpotifyAccountCreateFactory.build()

    @pytest.fixture
    def spotify_account_update(self) -> SpotifyAccountUpdate:
        return SpotifyAccountUpdateFactory.build()

    async def test_get_by_user_id__nominal(
        self,
        spotify_account: SpotifyAccount,
        spotify_account_repository: SpotifyAccountRepositoryPort,
    ) -> None:
        assert await spotify_account_repository.get_by_user_id(spotify_account.user_id)

    async def test_get_by_user_id__none(self, spotify_account_repository: SpotifyAccountRepositoryPort) -> None:
        assert await spotify_account_repository.get_by_user_id(uuid.uuid4()) is None

    async def test_create__nominal(
        self,
        user: User,
        spotify_account_create: SpotifyAccountCreate,
        spotify_account_repository: SpotifyAccountRepositoryPort,
    ) -> None:
        spotify_account_db = await spotify_account_repository.create(user.id, spotify_account_create)
        assert spotify_account_db is not None

        assert spotify_account_db.id
        assert spotify_account_db.user_id == user.id
        assert spotify_account_db.token_type == spotify_account_create.token_type
        assert spotify_account_db.token_access == spotify_account_create.token_access
        assert spotify_account_db.token_refresh == spotify_account_create.token_refresh
        assert spotify_account_db.token_expires_at == spotify_account_create.token_expires_at

    async def test_update__partial(
        self,
        spotify_account: SpotifyAccount,
        spotify_account_repository: SpotifyAccountRepositoryPort,
    ) -> None:
        spotify_account_data = SpotifyAccountUpdate(
            token_refresh="dummy-token-state",
            token_expires_at=datetime.now(UTC),
        )
        spotify_account_db = await spotify_account_repository.update(spotify_account.user_id, spotify_account_data)

        assert spotify_account_db.user_id == spotify_account.user_id

        assert spotify_account_db.token_type == spotify_account.token_type
        assert spotify_account_db.token_access == spotify_account.token_access

        assert spotify_account_db.token_refresh == spotify_account_data.token_refresh
        assert spotify_account_db.token_expires_at == spotify_account_data.token_expires_at

    async def test_update__all(
        self,
        spotify_account: SpotifyAccount,
        spotify_account_update: SpotifyAccountUpdate,
        spotify_account_repository: SpotifyAccountRepositoryPort,
    ) -> None:
        spotify_account_db = await spotify_account_repository.update(spotify_account.user_id, spotify_account_update)

        assert spotify_account_db.user_id == spotify_account.user_id

        assert spotify_account_db.token_type == spotify_account_update.token_type
        assert spotify_account_db.token_access == spotify_account_update.token_access
        assert spotify_account_db.token_refresh == spotify_account_update.token_refresh
        assert spotify_account_db.token_expires_at == spotify_account_update.token_expires_at

    async def test_delete__nominal(
        self,
        async_session_db: AsyncSession,
        spotify_account: SpotifyAccount,
        spotify_account_repository: SpotifyAccountRepositoryPort,
    ) -> None:
        await spotify_account_repository.delete(spotify_account.user_id)

        stmt = select(SpotifyAccountModel).where(SpotifyAccountModel.id == spotify_account.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar_one_or_none() is None
