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
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.models import AuthProviderStateModel
from museflow.infrastructure.adapters.database.models import AuthProviderTokenModel


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

    async def delete(self, user_id: uuid.UUID, provider: MusicProvider) -> None:
        stmt = delete(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user_id,
            AuthProviderStateModel.provider == provider,
        )
        await self.session.execute(stmt)


class OAuthProviderTokenSQLRepository(OAuthProviderTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderUserToken | None:
        stmt = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == user_id,
            AuthProviderTokenModel.provider == provider,
        )
        result = await self.session.execute(stmt)
        auth_token_db = result.scalar_one_or_none()
        return auth_token_db.to_entity() if auth_token_db else None

    async def upsert(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_in: OAuthProviderUserTokenCreateInput,
    ) -> OAuthProviderUserToken:
        token_data: dict[str, Any] = auth_token_in.model_dump()

        stmt = (
            pg_insert(AuthProviderTokenModel)
            .values(user_id=user_id, provider=provider, **token_data)
            .on_conflict_do_update(index_elements=["user_id", "provider"], set_=token_data)
            .returning(AuthProviderTokenModel)
        )
        result = await self.session.execute(stmt)
        auth_token_db = result.scalar_one()

        return auth_token_db.to_entity()

    async def update(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_in: OAuthProviderUserTokenUpdateInput,
        expected_token_access: str,
    ) -> OAuthProviderUserToken | None:
        update_data: dict[str, Any] = auth_token_in.model_dump(exclude_none=True)

        # The condition and the write are one statement: PostgreSQL locks the row, then checks the condition again on
        # its latest committed version, so a concurrent update of the same token can't slip in between.
        stmt = (
            update(AuthProviderTokenModel)
            .where(
                AuthProviderTokenModel.user_id == user_id,
                AuthProviderTokenModel.provider == provider,
                AuthProviderTokenModel.token_access == expected_token_access,
            )
            .values(**update_data)
            .returning(AuthProviderTokenModel)
        )
        result = await self.session.execute(stmt)
        auth_token_db = result.scalar_one_or_none()

        return auth_token_db.to_entity() if auth_token_db else None

    async def delete(self, user_id: uuid.UUID, provider: MusicProvider, expected_token_refresh: str) -> bool:
        stmt = (
            delete(AuthProviderTokenModel)
            .where(
                AuthProviderTokenModel.user_id == user_id,
                AuthProviderTokenModel.provider == provider,
                AuthProviderTokenModel.token_refresh == expected_token_refresh,
            )
            .returning(AuthProviderTokenModel.id)
        )
        result = await self.session.execute(stmt)
        deleted = result.scalar_one_or_none() is not None
        return deleted
