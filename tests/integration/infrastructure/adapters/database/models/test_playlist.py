from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.infrastructure.adapters.database.models import TasteProfileModel

from tests.integration.factories.models.playlist import PlaylistModelFactory


class TestPlaylistModel:
    async def test__profile_id__set_null_on_profile_delete(self, async_session_db: AsyncSession) -> None:
        playlist = await PlaylistModelFactory.create_async()
        assert playlist.profile_id is not None

        await async_session_db.execute(delete(TasteProfileModel).where(TasteProfileModel.id == playlist.profile_id))
        await async_session_db.refresh(playlist)

        assert playlist.profile_id is None
