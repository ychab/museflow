from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.user_delete import user_delete
from museflow.domain.entities.user import User
from museflow.domain.enums import PlaylistType
from museflow.infrastructure.adapters.database.models import User as UserModel
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.playlist import Playlist as PlaylistModel
from museflow.infrastructure.adapters.database.models.playlist import PlaylistTrack as PlaylistTrackModel

from tests.integration.factories.models.auth import AuthProviderStateModelFactory
from tests.integration.factories.models.auth import AuthProviderTokenFactory
from tests.integration.factories.models.blacklist import BlacklistedArtistModelFactory
from tests.integration.factories.models.blacklist import BlacklistedTrackModelFactory
from tests.integration.factories.models.llm import LLMUsageModelFactory
from tests.integration.factories.models.playlist import PlaylistModelFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.track import TrackModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TestUserDeleteUseCase:
    @pytest.fixture
    async def other_user_db(self, user: User) -> UserModel:
        """Gives both users exactly one row in each table."""
        other_user_db = await UserModelFactory.create_async()

        for user_id in (user.id, other_user_db.id):
            await AuthProviderStateModelFactory.create_async(user_id=user_id)
            await AuthProviderTokenFactory.create_async(user_id=user_id)
            await BlacklistedArtistModelFactory.create_async(user_id=user_id)
            await BlacklistedTrackModelFactory.create_async(user_id=user_id)

            track_db = await TrackModelFactory.create_async(user_id=user_id)
            profile_db = await TasteProfileModelFactory.create_async(user_id=user_id)
            playlist_db = await PlaylistModelFactory.create_async(
                user_id=user_id,
                type=PlaylistType.DISCOVERY,
                profile_id=profile_db.id,
                track_ids=[track_db.id],
            )
            await LLMUsageModelFactory.create_async(
                user_id=user_id, profile_id=profile_db.id, playlist_id=playlist_db.id
            )

        return other_user_db

    async def test__removes_only_the_user_data(
        self,
        async_session_db: AsyncSession,
        user: User,
        other_user_db: UserModel,
        uow: UnitOfWorkPort,
    ) -> None:
        await user_delete(user_id=user.id, uow=uow)

        # Goes through all the tables: a new one fails here until the fixture above fills it.
        tables = Base.metadata.sorted_tables
        counts = {
            table.name: (await async_session_db.execute(select(func.count()).select_from(table))).scalar_one()
            for table in tables
        }
        assert counts == dict.fromkeys(counts, 1)

        owners = {
            table.name: (await async_session_db.execute(select(table.c.user_id))).scalars().all()
            for table in tables
            if "user_id" in table.c
        }
        assert owners == dict.fromkeys(owners, [other_user_db.id])

        stmt_user = select(UserModel.id)
        assert (await async_session_db.execute(stmt_user)).scalars().all() == [other_user_db.id]

        stmt_playlist_track = select(PlaylistModel.user_id).join(
            PlaylistTrackModel,
            PlaylistTrackModel.playlist_id == PlaylistModel.id,
        )
        assert (await async_session_db.execute(stmt_playlist_track)).scalars().all() == [other_user_db.id]
