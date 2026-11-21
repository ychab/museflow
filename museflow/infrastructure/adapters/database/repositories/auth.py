import logging
import uuid
from datetime import UTC
from datetime import datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.inputs.auth import OAuthProviderUserTokenCreateInput
from museflow.application.inputs.auth import OAuthProviderUserTokenUpdateInput
from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.application.ports.security import TokenCipherPort
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import TokenDecryptionError
from museflow.infrastructure.adapters.database.models import AuthProviderStateModel
from museflow.infrastructure.adapters.database.models import AuthProviderTokenModel

logger = logging.getLogger(__name__)


class OAuthProviderStateSQLRepository(OAuthProviderStateRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, user_id: uuid.UUID, provider: MusicProvider, state: str) -> tuple[OAuthProviderState, bool]:
        stmt = (
            pg_insert(AuthProviderStateModel)
            .values(
                user_id=user_id,
                provider=provider,
                state=state,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "provider"],
                set_={
                    "state": state,
                    "updated_at": datetime.now(UTC),
                },
            )
            .returning(
                AuthProviderStateModel,
                text("(xmax = 0) AS was_created"),
            )
        )

        result = await self.session.execute(stmt)

        auth_state_db, created = result.one()

        return auth_state_db.to_entity(), created

    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderState | None:
        stmt = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user_id,
            AuthProviderStateModel.provider == provider,
        )
        result = await self.session.execute(stmt)
        auth_state_db = result.scalar_one_or_none()

        return auth_state_db.to_entity() if auth_state_db else None

    async def consume(self, state: str) -> OAuthProviderState | None:
        stmt = (
            delete(AuthProviderStateModel)
            .where(AuthProviderStateModel.state == state)
            .returning(AuthProviderStateModel)
        )
        result = await self.session.execute(stmt)
        auth_state_db = result.scalar_one_or_none()
        return auth_state_db.to_entity() if auth_state_db else None


class OAuthProviderTokenSQLRepository(OAuthProviderTokenRepository):
    """Encrypts the access and refresh tokens before they reach the database, and decrypts them on the way back.

    Each token is encrypted for its row and column (its context), deterministically: the compare-and-swap of `update`
    and `delete` encrypts the expected token and compares the bytes in SQL, in the same single statement as before.
    """

    def __init__(self, session: AsyncSession, token_cipher: TokenCipherPort) -> None:
        self.session = session
        self.token_cipher = token_cipher

    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderUserToken | None:
        stmt = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == user_id,
            AuthProviderTokenModel.provider == provider,
        )
        result = await self.session.execute(stmt)
        auth_token_db = result.scalar_one_or_none()

        if auth_token_db is None:
            return None

        try:
            auth_token = auth_token_db.to_entity(self.token_cipher)
        except TokenDecryptionError:
            # Known gap: no key rotation. A token encrypted with a former key is as good as gone, and a reconnect
            # replaces it.
            logger.warning(
                f"The {provider} token of user {user_id} can't be decrypted (encryption key changed?): the user must "
                "reconnect",
                extra={"user_id": str(user_id), "provider": provider},
            )
            return None

        return auth_token

    async def upsert(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_in: OAuthProviderUserTokenCreateInput,
    ) -> OAuthProviderUserToken:
        token_data: dict[str, Any] = auth_token_in.model_dump() | {
            "token_access": self._encrypt(auth_token_in.token_access, user_id, provider, "token_access"),
            "token_refresh": self._encrypt(auth_token_in.token_refresh, user_id, provider, "token_refresh"),
        }

        stmt = (
            pg_insert(AuthProviderTokenModel)
            .values(user_id=user_id, provider=provider, **token_data)
            .on_conflict_do_update(index_elements=["user_id", "provider"], set_=token_data)
            .returning(AuthProviderTokenModel)
        )
        result = await self.session.execute(stmt)
        auth_token_db = result.scalar_one()

        return auth_token_db.to_entity(self.token_cipher)

    async def update(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_in: OAuthProviderUserTokenUpdateInput,
        expected_token_access: str,
    ) -> OAuthProviderUserToken | None:
        update_data: dict[str, Any] = auth_token_in.model_dump(exclude_none=True)
        if auth_token_in.token_access is not None:
            update_data["token_access"] = self._encrypt(auth_token_in.token_access, user_id, provider, "token_access")
        if auth_token_in.token_refresh is not None:
            update_data["token_refresh"] = self._encrypt(
                auth_token_in.token_refresh, user_id, provider, "token_refresh"
            )

        # The condition and the write are one statement: PostgreSQL locks the row, then checks the condition again on
        # its latest committed version, so a concurrent update of the same token can't slip in between. The expected
        # token is encrypted like the stored one, so equal tokens give equal bytes: with each key, as a rotation may
        # not have encrypted it again yet.
        expected_token_access_encrypted = self._encrypt_with_each_key(
            expected_token_access, user_id, provider, "token_access"
        )
        stmt = (
            update(AuthProviderTokenModel)
            .where(
                AuthProviderTokenModel.user_id == user_id,
                AuthProviderTokenModel.provider == provider,
                AuthProviderTokenModel.token_access.in_(expected_token_access_encrypted),
            )
            .values(**update_data)
            .returning(AuthProviderTokenModel)
        )
        result = await self.session.execute(stmt)
        auth_token_db = result.scalar_one_or_none()

        return auth_token_db.to_entity(self.token_cipher) if auth_token_db else None

    async def delete(self, user_id: uuid.UUID, provider: MusicProvider, expected_token_refresh: str) -> bool:
        expected_token_refresh_encrypted = self._encrypt_with_each_key(
            expected_token_refresh, user_id, provider, "token_refresh"
        )
        stmt = (
            delete(AuthProviderTokenModel)
            .where(
                AuthProviderTokenModel.user_id == user_id,
                AuthProviderTokenModel.provider == provider,
                AuthProviderTokenModel.token_refresh.in_(expected_token_refresh_encrypted),
            )
            .returning(AuthProviderTokenModel.id)
        )
        result = await self.session.execute(stmt)
        deleted = result.scalar_one_or_none() is not None
        return deleted

    async def bulk_reencrypt(self) -> int:
        # Locked until the commit: a refresh of one of these tokens waits, instead of being overwritten by the value
        # read here. No remote call happens in this transaction.
        stmt = select(AuthProviderTokenModel).with_for_update()
        result = await self.session.execute(stmt)

        reencrypted = 0
        for auth_token_db in result.scalars():
            user_id = auth_token_db.user_id
            provider = auth_token_db.provider

            try:
                auth_token = auth_token_db.to_entity(self.token_cipher)
            except TokenDecryptionError:
                logger.warning(
                    f"The {provider} token of user {user_id} can't be decrypted with any key: left as it is, the user "
                    "must reconnect",
                    extra={"user_id": str(user_id), "provider": provider},
                )
                continue

            token_access = self._encrypt(auth_token.token_access, user_id, provider, "token_access")
            token_refresh = self._encrypt(auth_token.token_refresh, user_id, provider, "token_refresh")
            # Deterministic encryption: equal bytes mean the token is already under the current key
            if token_access == auth_token_db.token_access and token_refresh == auth_token_db.token_refresh:
                continue

            await self.session.execute(
                update(AuthProviderTokenModel)
                .where(AuthProviderTokenModel.id == auth_token_db.id)
                .values(token_access=token_access, token_refresh=token_refresh)
            )

            reencrypted += 1

        return reencrypted

    def _encrypt(self, token: str, user_id: uuid.UUID, provider: MusicProvider, column: str) -> bytes:
        return self.token_cipher.encrypt(
            token,
            context=AuthProviderTokenModel.get_token_context(user_id, provider, column),
        )

    def _encrypt_with_each_key(
        self,
        token: str,
        user_id: uuid.UUID,
        provider: MusicProvider,
        column: str,
    ) -> list[bytes]:
        return self.token_cipher.encrypt_with_each_key(
            token,
            context=AuthProviderTokenModel.get_token_context(user_id, provider, column),
        )
