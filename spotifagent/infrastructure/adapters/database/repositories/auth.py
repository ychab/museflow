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

from spotifagent.domain.entities.auth import OAuthProviderState
from spotifagent.domain.entities.auth import OAuthProviderUserToken
from spotifagent.domain.entities.auth import OAuthProviderUserTokenCreate
from spotifagent.domain.entities.auth import OAuthProviderUserTokenUpdate
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderTokenRepositoryPort
from spotifagent.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel
from spotifagent.infrastructure.adapters.database.models import AuthProviderToken as AuthProviderTokenModel


class OAuthProviderStateRepository(OAuthProviderStateRepositoryPort):
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

        return OAuthProviderState.model_validate(auth_state_db), created

    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderState | None:
        stmt = select(AuthProviderStateModel).where(
            AuthProviderStateModel.user_id == user_id,
            AuthProviderStateModel.provider == provider,
        )
        result = await self.session.execute(stmt)
        auth_state_db = result.scalar_one_or_none()

        return OAuthProviderState.model_validate(auth_state_db) if auth_state_db else None

    async def consume(self, state: str) -> OAuthProviderState | None:
        stmt_select = select(AuthProviderStateModel).where(AuthProviderStateModel.state == state)
        result = await self.session.execute(stmt_select)
        auth_state_db = result.scalar_one_or_none()

        if auth_state_db is not None:
            stmt_delete = delete(AuthProviderStateModel).where(AuthProviderStateModel.id == auth_state_db.id)
            await self.session.execute(stmt_delete)
            await self.session.commit()

        return OAuthProviderState.model_validate(auth_state_db) if auth_state_db else None


class OAuthProviderTokenRepository(OAuthProviderTokenRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID, provider: MusicProvider) -> OAuthProviderUserToken | None:
        stmt = select(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == str(user_id),
            AuthProviderTokenModel.provider == provider,
        )
        result = await self.session.execute(stmt)
        auth_token = result.scalar_one_or_none()
        return OAuthProviderUserToken.model_validate(auth_token) if auth_token else None

    async def create(
        self,
        user_id: uuid.UUID,
        provider: MusicProvider,
        auth_token_data: OAuthProviderUserTokenCreate,
    ) -> OAuthProviderUserToken | None:
        auth_token_dict: dict[str, Any] = auth_token_data.model_dump()
        auth_token_dict["user_id"] = str(user_id)
        auth_token_dict["provider"] = provider

        auth_token = AuthProviderTokenModel(**auth_token_dict)
        self.session.add(auth_token)
        await self.session.commit()

        await self.session.refresh(auth_token)
        return OAuthProviderUserToken.model_validate(auth_token)

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
        auth_token = result.scalar_one()
        await self.session.commit()

        await self.session.refresh(auth_token)
        return OAuthProviderUserToken.model_validate(auth_token)

    async def delete(self, user_id: uuid.UUID, provider: MusicProvider) -> None:
        stmt = delete(AuthProviderTokenModel).where(
            AuthProviderTokenModel.user_id == user_id,
            AuthProviderTokenModel.provider == provider,
        )

        await self.session.execute(stmt)
        await self.session.commit()
