import logging
import uuid
from datetime import UTC
from datetime import datetime
from typing import Final

from pydantic import SecretStr

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.auth import OAuthProviderUserTokenCreateInput
from museflow.application.inputs.auth import OAuthProviderUserTokenUpdateInput
from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.models import AuthProviderStateModel
from museflow.infrastructure.adapters.database.models import AuthProviderTokenModel
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderTokenSQLRepository
from museflow.infrastructure.adapters.security import AesSivTokenCipher
from museflow.infrastructure.config.settings.app import app_settings

from tests.integration.factories.models.user import UserModelFactory
from tests.unit.factories.inputs.auth import OAuthProviderUserTokenCreateInputFactory

FORMER_KEY: Final[SecretStr] = SecretStr("a-former-key-of-at-least-32-characters")
UNKNOWN_KEY: Final[SecretStr] = SecretStr("a-key-no-setting-holds-of-32-characters")


class TestOAuthProviderStateSQLRepository:
    async def test__upsert__create(
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

    async def test__upsert__update(
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

    async def test__get__nominal(
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

    async def test__get__invalid(
        self,
        auth_state_repository: OAuthProviderStateRepository,
        auth_state: OAuthProviderState,
    ) -> None:
        auth_state_invalid = await auth_state_repository.get(
            user_id=uuid.uuid4(),
            provider=auth_state.provider,
        )
        assert auth_state_invalid is None

    async def test__consume__nominal(
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

    async def test__consume__none(
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
    @pytest.fixture
    def auth_token_repository_former_key(self, async_session_db: AsyncSession) -> OAuthProviderTokenRepository:
        return OAuthProviderTokenSQLRepository(async_session_db, AesSivTokenCipher(key=FORMER_KEY))

    @pytest.fixture
    def auth_token_repository_rotated(self, async_session_db: AsyncSession) -> OAuthProviderTokenRepository:
        """Midway through a rotation: the current key encrypts, the former one still decrypts."""
        token_cipher = AesSivTokenCipher(key=app_settings.PROVIDER_TOKEN_ENCRYPTION_KEY, fallback_keys=[FORMER_KEY])
        return OAuthProviderTokenSQLRepository(async_session_db, token_cipher)

    @pytest.fixture
    async def auth_token_former_key(
        self,
        user: User,
        auth_token_create: OAuthProviderUserTokenCreateInput,
        auth_token_repository_former_key: OAuthProviderTokenRepository,
    ) -> OAuthProviderUserToken:
        return await auth_token_repository_former_key.upsert(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_create,
        )

    async def test__get__nominal(
        self,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        assert await auth_token_repository.get(user_id=auth_token.user_id, provider=auth_token.provider) == auth_token

    async def test__get__none(self, auth_token_repository: OAuthProviderTokenRepository) -> None:
        assert await auth_token_repository.get(uuid.uuid4(), provider=MusicProvider.SPOTIFY) is None

    async def test__get__encryption_key_changed(
        self,
        user: User,
        auth_token_create: OAuthProviderUserTokenCreateInput,
        auth_token_repository_former_key: OAuthProviderTokenRepository,
        auth_token_repository: OAuthProviderTokenRepository,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        await auth_token_repository_former_key.upsert(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_create,
        )

        with caplog.at_level(logging.WARNING):
            auth_token = await auth_token_repository.get(user_id=user.id, provider=MusicProvider.SPOTIFY)

        assert auth_token is None
        assert f"The spotify token of user {user.id} can't be decrypted" in caplog.text

    async def test__upsert__create(
        self,
        user: User,
        auth_token_create: OAuthProviderUserTokenCreateInput,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token_db = await auth_token_repository.upsert(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_create,
        )

        assert auth_token_db.id
        assert auth_token_db.user_id == user.id
        assert auth_token_db.provider == MusicProvider.SPOTIFY
        assert auth_token_db.token_type == auth_token_create.token_type
        assert auth_token_db.token_access == auth_token_create.token_access
        assert auth_token_db.token_refresh == auth_token_create.token_refresh
        assert auth_token_db.token_expires_at == auth_token_create.token_expires_at

    async def test__upsert__encrypted_at_rest(
        self,
        async_session_db: AsyncSession,
        user: User,
        auth_token_create: OAuthProviderUserTokenCreateInput,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        await auth_token_repository.upsert(
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_create,
        )

        stmt = select(AuthProviderTokenModel.token_access, AuthProviderTokenModel.token_refresh).where(
            AuthProviderTokenModel.user_id == user.id,
        )
        token_access_stored, token_refresh_stored = (await async_session_db.execute(stmt)).one()
        assert auth_token_create.token_access.encode() not in token_access_stored
        assert auth_token_create.token_refresh.encode() not in token_refresh_stored

    async def test__upsert__replace(
        self,
        async_session_db: AsyncSession,
        auth_token: OAuthProviderUserToken,
        auth_token_create: OAuthProviderUserTokenCreateInput,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token_db = await auth_token_repository.upsert(
            user_id=auth_token.user_id,
            provider=auth_token.provider,
            auth_token_in=auth_token_create,
        )

        assert auth_token_db.id == auth_token.id
        assert auth_token_db.token_type == auth_token_create.token_type
        assert auth_token_db.token_access == auth_token_create.token_access
        assert auth_token_db.token_refresh == auth_token_create.token_refresh
        assert auth_token_db.token_expires_at == auth_token_create.token_expires_at

        stmt = select(func.count()).where(
            AuthProviderTokenModel.user_id == auth_token.user_id,
            AuthProviderTokenModel.provider == auth_token.provider,
        )
        assert await async_session_db.scalar(stmt) == 1

    async def test__update__partial(
        self,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token_in = OAuthProviderUserTokenUpdateInput(
            token_refresh="dummy-token-state",
            token_expires_at=datetime.now(UTC),
        )
        auth_token_db = await auth_token_repository.update(
            user_id=auth_token.user_id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_in,
            expected_token_access=auth_token.token_access,
        )

        assert auth_token_db is not None
        assert auth_token_db.user_id == auth_token.user_id
        assert auth_token_db.provider == MusicProvider.SPOTIFY
        assert auth_token_db.token_type == auth_token.token_type
        assert auth_token_db.token_access == auth_token.token_access
        assert auth_token_db.token_refresh == auth_token_in.token_refresh
        assert auth_token_db.token_expires_at == auth_token_in.token_expires_at

    async def test__update__token_refresh_kept(
        self,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        # Spotify doesn't always issue a new refresh token: the stored one is kept, and still decrypts
        auth_token_in = OAuthProviderUserTokenUpdateInput(token_access="dummy-new-token-access")
        auth_token_db = await auth_token_repository.update(
            user_id=auth_token.user_id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_in,
            expected_token_access=auth_token.token_access,
        )

        assert auth_token_db is not None
        assert auth_token_db.token_access == auth_token_in.token_access
        assert auth_token_db.token_refresh == auth_token.token_refresh

    async def test__update__all(
        self,
        auth_token: OAuthProviderUserToken,
        auth_token_update: OAuthProviderUserTokenUpdateInput,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token_db = await auth_token_repository.update(
            user_id=auth_token.user_id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_update,
            expected_token_access=auth_token.token_access,
        )

        assert auth_token_db is not None
        assert auth_token_db.user_id == auth_token.user_id
        assert auth_token_db.provider == MusicProvider.SPOTIFY
        assert auth_token_db.token_type == auth_token_update.token_type
        assert auth_token_db.token_access == auth_token_update.token_access
        assert auth_token_db.token_refresh == auth_token_update.token_refresh
        assert auth_token_db.token_expires_at == auth_token_update.token_expires_at

    async def test__update__token_access_changed(
        self,
        auth_token: OAuthProviderUserToken,
        auth_token_update: OAuthProviderUserTokenUpdateInput,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token_db = await auth_token_repository.update(
            user_id=auth_token.user_id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_update,
            expected_token_access="replaced-by-another-session",
        )

        assert auth_token_db is None
        assert await auth_token_repository.get(user_id=auth_token.user_id, provider=auth_token.provider) == auth_token

    async def test__delete__nominal(
        self,
        async_session_db: AsyncSession,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        deleted = await auth_token_repository.delete(
            user_id=auth_token.user_id,
            provider=auth_token.provider,
            expected_token_refresh=auth_token.token_refresh,
        )

        assert deleted is True
        stmt = select(AuthProviderTokenModel).where(AuthProviderTokenModel.id == auth_token.id)
        result = await async_session_db.execute(stmt)
        assert result.scalar_one_or_none() is None

    async def test__delete__token_refresh_changed(
        self,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        deleted = await auth_token_repository.delete(
            user_id=auth_token.user_id,
            provider=auth_token.provider,
            expected_token_refresh="replaced-by-another-session",
        )

        assert deleted is False
        assert await auth_token_repository.get(user_id=auth_token.user_id, provider=auth_token.provider) == auth_token

    async def test__get__fallback_key(
        self,
        auth_token_former_key: OAuthProviderUserToken,
        auth_token_repository_rotated: OAuthProviderTokenRepository,
    ) -> None:
        auth_token = await auth_token_repository_rotated.get(
            user_id=auth_token_former_key.user_id, provider=MusicProvider.SPOTIFY
        )
        assert auth_token == auth_token_former_key

    async def test__update__fallback_key(
        self,
        auth_token_former_key: OAuthProviderUserToken,
        auth_token_update: OAuthProviderUserTokenUpdateInput,
        auth_token_repository_rotated: OAuthProviderTokenRepository,
        auth_token_repository: OAuthProviderTokenRepository,
    ) -> None:
        auth_token_db = await auth_token_repository_rotated.update(
            user_id=auth_token_former_key.user_id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=auth_token_update,
            expected_token_access=auth_token_former_key.token_access,
        )

        assert auth_token_db is not None
        assert auth_token_db.token_access == auth_token_update.token_access
        # Both tokens written again, with the current key only
        assert (
            await auth_token_repository.get(user_id=auth_token_former_key.user_id, provider=MusicProvider.SPOTIFY)
            == auth_token_db
        )

    async def test__delete__fallback_key(
        self,
        auth_token_former_key: OAuthProviderUserToken,
        auth_token_repository_rotated: OAuthProviderTokenRepository,
    ) -> None:
        deleted = await auth_token_repository_rotated.delete(
            user_id=auth_token_former_key.user_id,
            provider=MusicProvider.SPOTIFY,
            expected_token_refresh=auth_token_former_key.token_refresh,
        )
        assert deleted is True

    async def test__bulk_reencrypt__nominal(
        self,
        async_session_db: AsyncSession,
        auth_token_former_key: OAuthProviderUserToken,
        auth_token_repository_rotated: OAuthProviderTokenRepository,
        auth_token_repository: OAuthProviderTokenRepository,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        user_current_key = await UserModelFactory.create_async()
        auth_token_current_key = await auth_token_repository.upsert(
            user_id=user_current_key.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=OAuthProviderUserTokenCreateInputFactory.build(),
        )
        user_unknown_key = await UserModelFactory.create_async()
        await OAuthProviderTokenSQLRepository(async_session_db, AesSivTokenCipher(key=UNKNOWN_KEY)).upsert(
            user_id=user_unknown_key.id,
            provider=MusicProvider.SPOTIFY,
            auth_token_in=OAuthProviderUserTokenCreateInputFactory.build(),
        )

        with caplog.at_level(logging.WARNING):
            reencrypted = await auth_token_repository_rotated.bulk_reencrypt()

        assert reencrypted == 1
        assert f"The spotify token of user {user_unknown_key.id} can't be decrypted with any key" in caplog.text
        # The former key can go: the current one alone reads every token it could read
        assert (
            await auth_token_repository.get(user_id=auth_token_former_key.user_id, provider=MusicProvider.SPOTIFY)
            == auth_token_former_key
        )
        assert (
            await auth_token_repository.get(user_id=user_current_key.id, provider=MusicProvider.SPOTIFY)
            == auth_token_current_key
        )
