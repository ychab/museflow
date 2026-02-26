import uuid
from datetime import UTC
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.ports.repositories.auth import OAuthProviderStateRepository
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.ports.security import StateTokenGeneratorPort
from museflow.domain.schemas.auth import OAuthProviderUserTokenCreate
from museflow.domain.schemas.auth import OAuthProviderUserTokenUpdate
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel
from museflow.infrastructure.adapters.database.models import AuthProviderToken as AuthProviderTokenModel


class TestOAuthProviderStateSQLRepository:
    async def test_upsert__create(
        self,
        auth_state_repository: OAuthProviderStateRepository,
        state_token_generator: StateTokenGeneratorPort,
        user: User,
    ) -> None:
        state = state_token_generator.generate()

        auth_state, created = await auth_state_repository.upsert(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            state=state,
        )

        assert created is True
        assert auth_state.user_id == user.id
        assert auth_state.provider == MusicProvider.SPOTIFY
        assert auth_state.state == state

    async def test_upsert__update(
        self,
        auth_state_repository: OAuthProviderStateRepository,
        state_token_generator: StateTokenGeneratorPort,
        auth_state: OAuthProviderState,
    ) -> None:
        state = state_token_generator.generate()

        auth_state_updated, created = await auth_state_repository.upsert(
            user_id=auth_state.user_id,
            provider=auth_state.provider,
            state=state,
        )

        assert created is False
        assert auth_state_updated.id == auth_state.id
        assert auth_state_updated.user_id == auth_state.user_id
        assert auth_state_updated.provider == auth_state.provider
        assert auth_state_updated.state == state != auth_state.state
        assert auth_state_updated.updated_at >= auth_state.updated_at

    async def test_get__nominal(
        self,
        auth_state_repository: OAuthProviderStateRepository,
        auth_state: OAuthProviderState,
    ) -> None:
        auth_state_duplicate = await auth_state_repository.get(
            user_id=auth_state.user_id,
            provider=auth_state.provider,
        )

        assert auth_state_duplicate is not None
        assert auth_state_duplicate.user_id == auth_state.user_id
        assert auth_state_duplicate.provider == auth_state.provider
        assert auth_state_duplicate.state == auth_state.state

    async def test_get__invalid(
        self,
        auth_state_repository: OAuthProviderStateRepository,
        auth_state: OAuthProviderState,
    ) -> None:
        auth_state_invalid = await auth_state_repository.get(
            user_id=uuid.uuid4(),
            provider=auth_state.provider,
        )
        assert auth_state_invalid is None

    async def test_consume__nominal(
        self,
        async_session_db: AsyncSession,
        auth_state_repository: OAuthProviderStateRepository,
        auth_state: OAuthProviderState,
    ) -> None:
        auth_state_consumed = await auth_state_repository.consume(state=auth_state.state)

        assert auth_state_consumed is not None
        assert auth_state_consumed.user_id == auth_state.user_id
        assert auth_state_consumed.provider == auth_state.provider
        assert auth_state_consumed.state == auth_state.state

        with pytest.raises(SQLAlchemyError):
            await async_session_db.refresh(auth_state)

    async def test_consume__none(
        self,
        async_session_db: AsyncSession,
        auth_state_repository: OAuthProviderStateRepository,
        auth_state: OAuthProviderState,
    ) -> None:
        auth_state_unknown = await auth_state_repository.consume(state="dummy-state")
        assert auth_state_unknown is None

        stmt = select(AuthProviderStateModel).where(AuthProviderStateModel.id == auth_state.id)
        result = await async_session_db.execute(stmt)
        auth_state_db = result.scalar_one_or_none()

        assert auth_state_db is not None


class TestOAuthProviderTokenSQLRepository:
    async def test_get__nominal(
        self,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        assert await auth_token_repository.get(user_id=auth_token.user_id, provider=auth_token.provider)

    async def test_get__none(self, auth_token_repository: OAuthProviderTokenRepository) -> None:
        assert await auth_token_repository.get(uuid.uuid4(), provider=MusicProvider.SPOTIFY) is None

    async def test_create__nominal(
        self,
        user: User,
        auth_token_create: OAuthProviderUserTokenCreate,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token_db = await auth_token_repository.create(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_data=auth_token_create,
        )
        assert auth_token_db is not None

        assert auth_token_db.id
        assert auth_token_db.user_id == user.id
        assert auth_token_db.provider == MusicProvider.SPOTIFY
        assert auth_token_db.token_type == auth_token_create.token_type
        assert auth_token_db.token_access == auth_token_create.token_access
        assert auth_token_db.token_refresh == auth_token_create.token_refresh
        assert auth_token_db.token_expires_at == auth_token_create.token_expires_at

    async def test_update__partial(
        self,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token_data = OAuthProviderUserTokenUpdate(
            token_refresh="dummy-token-state",
            token_expires_at=datetime.now(UTC),
        )
        auth_token_db = await auth_token_repository.update(
            user_id=auth_token.user_id,
            provider=MusicProvider.SPOTIFY,
            auth_token_data=auth_token_data,
        )

        assert auth_token_db.user_id == auth_token.user_id
        assert auth_token_db.provider == MusicProvider.SPOTIFY
        assert auth_token_db.token_type == auth_token.token_type
        assert auth_token_db.token_access == auth_token.token_access
        assert auth_token_db.token_refresh == auth_token_data.token_refresh
        assert auth_token_db.token_expires_at == auth_token_data.token_expires_at

    async def test_update__all(
        self,
        auth_token: OAuthProviderUserToken,
        auth_token_update: OAuthProviderUserTokenUpdate,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token_db = await auth_token_repository.update(
            user_id=auth_token.user_id,
            provider=MusicProvider.SPOTIFY,
            auth_token_data=auth_token_update,
        )

        assert auth_token_db.user_id == auth_token.user_id
        assert auth_token_db.provider == MusicProvider.SPOTIFY
        assert auth_token_db.token_type == auth_token_update.token_type
        assert auth_token_db.token_access == auth_token_update.token_access
        assert auth_token_db.token_refresh == auth_token_update.token_refresh
        assert auth_token_db.token_expires_at == auth_token_update.token_expires_at

    async def test_delete__nominal(
        self,
        async_session_db: AsyncSession,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        await auth_token_repository.delete(user_id=auth_token.user_id, provider=auth_token.provider)

        stmt = select(AuthProviderTokenModel).where(AuthProviderTokenModel.id == auth_token.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar_one_or_none() is None
