import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from spotifagent.domain.entities.auth import OAuthProviderState
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.domain.ports.security import StateTokenGeneratorPort
from spotifagent.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel


class TestOAuthProviderStateRepository:
    async def test_upsert__create(
        self,
        auth_state_repository: OAuthProviderStateRepositoryPort,
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
        auth_state_repository: OAuthProviderStateRepositoryPort,
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
        auth_state_repository: OAuthProviderStateRepositoryPort,
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
        auth_state_repository: OAuthProviderStateRepositoryPort,
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
        auth_state_repository: OAuthProviderStateRepositoryPort,
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
        auth_state_repository: OAuthProviderStateRepositoryPort,
        auth_state: OAuthProviderState,
    ) -> None:
        auth_state_unknown = await auth_state_repository.consume(state="dummy-state")
        assert auth_state_unknown is None

        stmt = select(AuthProviderStateModel).where(AuthProviderStateModel.id == auth_state.id)
        result = await async_session_db.execute(stmt)
        auth_state_db = result.scalar_one_or_none()

        assert auth_state_db is not None
