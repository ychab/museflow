from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.inputs.rate import RatingEntryInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.ratings_import import import_ratings
from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.infrastructure.adapters.database.models import Track as TrackModel

from tests.integration.factories.models.track import TrackModelFactory


class TestImportRatingsUseCase:
    async def test__nominal(self, user: User, uow: UnitOfWorkPort, async_session_db: AsyncSession) -> None:
        rated_db = await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=False)
        skipped_db = await TrackModelFactory.create_async(user_id=user.id, score=None, score_skipped=False)
        entries = [
            RatingEntryInput(fingerprint=rated_db.fingerprint, score=9),
            RatingEntryInput(fingerprint=skipped_db.fingerprint, score_skipped=True),
            RatingEntryInput(fingerprint="unknown-fp", score=5),
        ]

        result = await import_ratings(user_id=user.id, entries=entries, uow=uow)

        assert result.imported_count == 1
        assert result.skipped_count == 1
        assert result.created_count == 0
        assert result.not_found_count == 1

        stmt = select(TrackModel).where(TrackModel.id.in_([rated_db.id, skipped_db.id]))
        tracks_db = {track.id: track for track in (await async_session_db.execute(stmt)).scalars()}
        assert tracks_db[rated_db.id].score == 9
        assert tracks_db[skipped_db.id].score_skipped is True

    async def test__missing_track__recreated(
        self,
        user: User,
        uow: UnitOfWorkPort,
        async_session_db: AsyncSession,
    ) -> None:
        entries = [
            RatingEntryInput(
                fingerprint="discovery-fp",
                score=8,
                name="Fictional Song",
                artists=["Fictional Artist"],
                album_name="Fictional Album",
                source=TrackSource.DISCOVERY,
                provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id="spotify-id")],
            ),
            RatingEntryInput(
                fingerprint="skipped-fp",
                score_skipped=True,
                name="Other Song",
                artists=["Other Artist"],
                provider_links=[ProviderLink(provider=MusicProvider.SPOTIFY, provider_id="other-id")],
            ),
        ]

        result = await import_ratings(user_id=user.id, entries=entries, uow=uow)

        assert result.imported_count == 1
        assert result.skipped_count == 1
        assert result.created_count == 2
        assert result.not_found_count == 0

        stmt = select(TrackModel).where(TrackModel.user_id == user.id)
        tracks_db = {track.fingerprint: track for track in (await async_session_db.execute(stmt)).scalars()}
        discovery_db = tracks_db["discovery-fp"]
        assert discovery_db.score == 8
        assert discovery_db.name == "Fictional Song"
        assert discovery_db.artists == ["Fictional Artist"]
        assert discovery_db.album_name == "Fictional Album"
        assert discovery_db.source == TrackSource.DISCOVERY
        assert discovery_db.provider_links == [{"provider": "spotify", "provider_id": "spotify-id"}]
        assert tracks_db["skipped-fp"].score_skipped is True
        assert tracks_db["skipped-fp"].source == TrackSource.HISTORY
