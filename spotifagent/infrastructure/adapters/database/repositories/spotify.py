import uuid
from typing import Any

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from spotifagent.domain.entities.spotify import SpotifyAccount
from spotifagent.domain.entities.spotify import SpotifyAccountCreate
from spotifagent.domain.entities.spotify import SpotifyAccountUpdate
from spotifagent.domain.ports.repositories.spotify import SpotifyAccountRepositoryPort
from spotifagent.infrastructure.adapters.database.models import SpotifyAccount as SpotifyAccountModel


class SpotifyAccountRepository(SpotifyAccountRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> SpotifyAccount | None:
        stmt = select(SpotifyAccountModel).where(SpotifyAccountModel.user_id == str(user_id))
        result = await self.session.execute(stmt)
        spotify_account = result.scalar_one_or_none()
        return SpotifyAccount.model_validate(spotify_account) if spotify_account else None

    async def create(self, user_id: uuid.UUID, spotify_account_data: SpotifyAccountCreate) -> SpotifyAccount | None:
        spotify_account_dict: dict[str, Any] = spotify_account_data.model_dump()
        spotify_account_dict["user_id"] = str(user_id)

        spotify_account = SpotifyAccountModel(**spotify_account_dict)
        self.session.add(spotify_account)
        await self.session.commit()

        await self.session.refresh(spotify_account)
        return SpotifyAccount.model_validate(spotify_account)

    async def update(self, user_id: uuid.UUID, spotify_account_data: SpotifyAccountUpdate) -> SpotifyAccount:
        update_data: dict[str, Any] = spotify_account_data.model_dump(exclude_none=True)

        stmt = (
            update(SpotifyAccountModel)
            .where(SpotifyAccountModel.user_id == user_id)
            .values(**update_data)
            .returning(SpotifyAccountModel)
        )
        result = await self.session.execute(stmt)
        spotify_account = result.scalar_one()
        await self.session.commit()

        await self.session.refresh(spotify_account)
        return SpotifyAccount.model_validate(spotify_account)

    async def delete(self, user_id: uuid.UUID) -> None:
        stmt = delete(SpotifyAccountModel).where(SpotifyAccountModel.user_id == user_id)

        await self.session.execute(stmt)
        await self.session.commit()
