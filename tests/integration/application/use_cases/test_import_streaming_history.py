from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Final

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.history import StreamingHistoryImportConfigInput
from museflow.application.ports.repositories.music import TrackRepository
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryReport
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryUseCase
from museflow.domain.entities.user import User
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.adapters.providers.spotify.history import SpotifyStreamingHistoryAdapter

from tests import ASSETS_DIR
from tests.integration.factories.models.music import TrackModelFactory

HISTORY_DIR: Final[Path] = ASSETS_DIR / "history" / "spotify" / "samples"


class TestImportStreamingHistorySpotifyUseCase:
    @pytest.fixture
    def track_ids(self) -> list[str]:
        return [
            # Same ID's as the history JSON files.
            "6wb6zxkNTBtcYVkXcvNyJp",
            "76v0OHTbZGeOZYmaLtEDhQ",
            "5BuWeANxxuVOZdTCgnaOnp",
            "4BqYFb5LHhRmmTDsPyUmQg",
        ]

    @pytest.fixture
    def use_case(
        self,
        track_repository: TrackRepository,
        spotify_streaming_history: SpotifyStreamingHistoryAdapter,
    ) -> ImportStreamingHistoryUseCase:
        return ImportStreamingHistoryUseCase(
            track_repository=track_repository,
            streaming_history=spotify_streaming_history,
        )

    async def test__nominal(
        self,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
    ) -> None:
        """
        Streaming_History_Audio_2017-2018_1.json : read=3, skip_dur=1, skip_uri=0 → 2 ids
        Streaming_History_Audio_2023-2024_11.json: read=3, skip_dur=1, skip_uri=0 → 2 ids
        Total: read=6, skip_dur=2, skip_uri=0, unique_track_ids=4
        """
        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(
                directory=HISTORY_DIR,
                min_ms_played=30_000,
            ),
        )

        assert report == ImportStreamingHistoryReport(
            items_read=6,
            items_skipped_no_timestamp=0,
            items_skipped_short_play=2,
            items_skipped_no_track_id=0,
            unique_track_ids=4,
            tracks_already_known=0,
            tracks_played_at_updated=0,
            tracks_created=4,
            tracks_purged=0,
        )

    async def test__purge(
        self,
        async_session_db: AsyncSession,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
    ) -> None:
        # Create 3 HISTORY tracks for the user to purge.
        tracks = await TrackModelFactory.create_batch_async(
            size=3,
            user_id=user.id,
            provider=MusicProvider.SPOTIFY,
        )
        track_ids = [track.id for track in tracks]

        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(
                directory=HISTORY_DIR,
                purge=True,
            ),
        )

        assert report == ImportStreamingHistoryReport(
            items_read=6,
            items_skipped_no_timestamp=0,
            items_skipped_short_play=2,
            items_skipped_no_track_id=0,
            unique_track_ids=4,
            tracks_already_known=0,
            tracks_played_at_updated=0,
            tracks_created=4,
            tracks_purged=3,
        )

        stmt = select(func.count()).select_from(TrackModel).where(TrackModel.id.in_(track_ids))
        count = (await async_session_db.execute(stmt)).scalar()
        assert count == 0

    async def test__known_tracks__played_at_updated(
        self,
        async_session_db: AsyncSession,
        user: User,
        track_ids: list[str],
        use_case: ImportStreamingHistoryUseCase,
    ) -> None:
        expected_played_at = {
            track_ids[0]: datetime(2017, 1, 10, 12, 34, 10, tzinfo=UTC),
            track_ids[1]: datetime(2017, 1, 10, 12, 36, 36, tzinfo=UTC),
            track_ids[2]: datetime(2023, 4, 15, 10, 50, 44, tzinfo=UTC),
            track_ids[3]: datetime(2023, 4, 15, 10, 53, 18, tzinfo=UTC),
        }
        old_played_at = datetime(2000, 1, 1, tzinfo=UTC)

        for track_id in track_ids:
            await TrackModelFactory.create_async(
                user_id=user.id,
                provider=MusicProvider.SPOTIFY,
                played_at=old_played_at,
                provider_id=track_id,
            )

        report = await use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(
                directory=HISTORY_DIR,
                min_ms_played=30_000,
            ),
        )

        assert report.tracks_played_at_updated == 4
        assert report.tracks_created == 0

        results = await async_session_db.execute(
            select(TrackModel).where(
                TrackModel.user_id == user.id,
                TrackModel.provider_id.in_(track_ids),
            )
        )
        tracks_by_id = {t.provider_id: t for t in results.scalars().all()}
        for track_id, expected in expected_played_at.items():
            assert tracks_by_id[track_id].played_at == expected, f"Wrong played_at for {track_id}"
