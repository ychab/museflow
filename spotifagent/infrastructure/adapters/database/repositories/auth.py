import uuid
from datetime import UTC
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from spotifagent.domain.entities.auth import OAuthProviderState
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.infrastructure.adapters.database.models import AuthProviderState as AuthProviderStateModel


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
