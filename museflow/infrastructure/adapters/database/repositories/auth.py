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

from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.ports.repositories.auth import OAuthProviderStateRepository
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.schemas.auth import OAuthProviderUserTokenCreate
from museflow.domain.schemas.auth import OAuthProviderUserTokenUpdate
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel
from museflow.infrastructure.adapters.database.models import AuthProviderToken as AuthProviderTokenModel


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
        await self.session.commit()

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
        stmt_select = select(AuthProviderStateModel).where(AuthProviderStateModel.state == state)
        result = await self.session.execute(stmt_select)
        auth_state_db = result.scalar_one_or_none()

        if auth_state_db is not None:
            stmt_delete = delete(AuthProviderStateModel).where(AuthProviderStateModel.id == auth_state_db.id)
            await self.session.execute(stmt_delete)
            await self.session.commit()

        return auth_state_db.to_entity() if auth_state_db else None


class OAuthProviderTokenSQLRepository(OAuthProviderTokenRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderUserToken | None:
        stmt = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == str(user_id),
            AuthProviderTokenModel.provider == provider,
        )
        result = await self.session.execute(stmt)
        auth_token_db = result.scalar_one_or_none()
        return auth_token_db.to_entity() if auth_token_db else None

    async def create(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_data: OAuthProviderUserTokenCreate,
    ) -> OAuthProviderUserToken | None:
        auth_token_dict: dict[str, Any] = auth_token_data.model_dump()
        auth_token_dict["user_id"] = str(user_id)
        auth_token_dict["provider"] = provider

        auth_token_db = AuthProviderTokenModel(**auth_token_dict)
        self.session.add(auth_token_db)
        await self.session.commit()

        await self.session.refresh(auth_token_db)
        return auth_token_db.to_entity()

    async def update(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_data: OAuthProviderUserTokenUpdate,
    ) -> OAuthProviderUserToken:
        update_data: dict[str, Any] = auth_token_data.model_dump(exclude_none=True)

        stmt = (
            update(AuthProviderTokenModel)
            .where(
                AuthProviderTokenModel.user_id == user_id,
                AuthProviderTokenModel.provider == provider,
            )
            .values(**update_data)
            .returning(AuthProviderTokenModel)
        )
        result = await self.session.execute(stmt)
        auth_token_db = result.scalar_one()
        await self.session.commit()

        await self.session.refresh(auth_token_db)
        return auth_token_db.to_entity()

    async def delete(self, user_id: uuid.UUID, provider: MusicProvider) -> None:
        stmt = delete(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == user_id,
            AuthProviderTokenModel.provider == provider,
        )

        await self.session.execute(stmt)
        await self.session.commit()
