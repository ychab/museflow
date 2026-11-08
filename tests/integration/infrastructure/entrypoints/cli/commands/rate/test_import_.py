from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.domain.entities.user import User
from museflow.domain.enums import TrackSource
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.entrypoints.cli.commands.enrich.import_ import enrich_import_logic
from museflow.infrastructure.entrypoints.cli.commands.rate.export import rate_export_logic
from museflow.infrastructure.entrypoints.cli.commands.rate.import_ import rate_import_logic

from tests.integration.factories.models.track import TrackModelFactory


class TestRateImportLogic:
    async def test__nominal(self, user: User, async_session_db: AsyncSession) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, score=None)
        data = [{"fingerprint": track_db.fingerprint, "score": 9}]

        result = await rate_import_logic(email=user.email, data=data)

        assert result.imported_count == 1
        assert result.not_found_count == 0

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 9

    async def test__reimport_overrides(self, user: User, async_session_db: AsyncSession) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, score=3)

        await rate_import_logic(email=user.email, data=[{"fingerprint": track_db.fingerprint, "score": 9}])
        await rate_import_logic(email=user.email, data=[{"fingerprint": track_db.fingerprint, "score": 5}])

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score == 5

    async def test__score_skipped_entry__persists_flag(
        self,
        user: User,
        async_session_db: AsyncSession,
    ) -> None:
        track_db = await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=False)
        data = [{"fingerprint": track_db.fingerprint, "score_skipped": True}]

        result = await rate_import_logic(email=user.email, data=data)

        assert result.skipped_count == 1
        assert result.imported_count == 0

        stmt = select(TrackModel).where(TrackModel.id == track_db.id)
        updated = (await async_session_db.execute(stmt)).scalar_one()
        assert updated.score_skipped is True

    async def test__reset__discovery_track_kept(self, user: User, async_session_db: AsyncSession) -> None:
        # A discovery rated but never played: the streaming history import does not bring it back after a reset
        track_db = await TrackModelFactory.create_async(user_id=user.id, source=TrackSource.DISCOVERY, score=8)
        data = await rate_export_logic(email=user.email)
        await async_session_db.execute(delete(TrackModel).where(TrackModel.user_id == user.id))

        result = await rate_import_logic(email=user.email, data=data)
        # The enrichment import then finds the recreated track
        enrichment = await enrich_import_logic(
            email=user.email,
            data=[{"fingerprint": track_db.fingerprint, "genres": ["folk"]}],
        )

        assert result.created_count == 1
        assert result.imported_count == 1
        assert result.not_found_count == 0
        assert enrichment.imported_count == 1

        stmt = select(TrackModel).where(TrackModel.user_id == user.id)
        restored = (await async_session_db.execute(stmt)).scalar_one()
        assert restored.id != track_db.id
        assert restored.fingerprint == track_db.fingerprint
        assert restored.name == track_db.name
        assert restored.artists == track_db.artists
        assert restored.album_name == track_db.album_name
        assert restored.provider_links == track_db.provider_links
        assert restored.source == TrackSource.DISCOVERY
        assert restored.score == 8
        assert restored.genres == ["folk"]
