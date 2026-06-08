from unittest import mock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.entrypoints.cli.commands.rate.playlist import rate_playlist_logic

from tests.integration.factories.models.discovery import DiscoveryPlaylistModelFactory
from tests.integration.factories.models.music import TrackModelFactory


class TestRatePlaylistLogic:
    async def test__nominal(
        self,
        async_session_db: AsyncSession,
        user: User,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id)
        pl_db = await DiscoveryPlaylistModelFactory.create_async(user_id=user.id, track_ids=[track_db.id])

        with mock.patch("typer.prompt", return_value="8"):
            with mock.patch("typer.confirm", return_value=False):
                await rate_playlist_logic(playlist_id=pl_db.id, email=user.email)

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 8
