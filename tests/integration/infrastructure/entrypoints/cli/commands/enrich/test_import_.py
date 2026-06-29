from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.user import User
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.entrypoints.cli.commands.enrich.import_ import import_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestEnrichImportLogic:
    async def test__nominal(self, user: User, async_session_db: AsyncSession) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, genres=[], moods=[])
        data = [{"fingerprint": track_db.fingerprint, "genres": ["folk", "indie-folk"], "moods": ["melancholic"]}]

        result = await import_logic(email=user.email, data=data)

        assert result.imported_count == 1
        assert result.not_found_count == 0

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.genres == ["folk", "indie-folk"]
        assert updated.moods == ["melancholic"]

    async def test__reimport_overrides(self, user: User, async_session_db: AsyncSession) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, genres=["rock"], moods=["energetic"])

        await import_logic(
            email=user.email,
            data=[{"fingerprint": track_db.fingerprint, "genres": ["rock", "indie-rock"], "moods": []}],
        )
        await import_logic(
            email=user.email,
            data=[{"fingerprint": track_db.fingerprint, "genres": ["folk", "indie-folk"], "moods": ["chill"]}],
        )

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.genres == ["folk", "indie-folk"]
        assert updated.moods == ["chill"]
