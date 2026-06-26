from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Final

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.application.inputs.history import StreamingHistoryImportConfigInput
from museflow.application.ports.repositories.track import TrackRepository
from museflow.application.use_cases.history_import import ImportStreamingHistoryReport
from museflow.application.use_cases.history_import import ImportStreamingHistoryUseCase
from museflow.domain.entities.user import User
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models import Track as TrackModel
from museflow.infrastructure.adapters.providers.spotify.history import SpotifyStreamingHistoryAdapter

from tests import ASSETS_DIR
from tests.integration.factories.models.track import TrackModelFactory

HISTORY_DIR: Final[Path] = ASSETS_DIR / "history" / "spotify" / "samples"
REIMPORT_HISTORY_DIR: Final[Path] = ASSETS_DIR / "history" / "spotify" / "reimport"


class TestImportStreamingHistorySpotifyUseCase:
    @pytest.fixture
    def sample_fingerprints(self) -> dict[str, str]:
        # Fingerprints computed via generate_fingerprint(name, [artist]):
        # history_2017_2018.json: "No Type"/"Rae Sremmurd", "This Could Be Us"/"Rae Sremmurd"
        # history_2023_2024.json: "M.I.A"/"Kombo the X Writer", "No le hables de amor"/"BENGOCHEA"
        return {
            "6wb6zxkNTBtcYVkXcvNyJp": "no type|rae sremmurd",
            "76v0OHTbZGeOZYmaLtEDhQ": "this could be us|rae sremmurd",
            "5BuWeANxxuVOZdTCgnaOnp": "mia|kombo the x writer",
            "4BqYFb5LHhRmmTDsPyUmQg": "no le hables de amor|bengochea",
        }

    @pytest.fixture
    def track_ids(self, sample_fingerprints: dict[str, str]) -> list[str]:
        return list(sample_fingerprints.keys())

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
            plays_total=4,
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
            plays_total=4,
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
        sample_fingerprints: dict[str, str],
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

        # Create tracks with fingerprints matching the history files so they are recognised as known.
        for provider_id, fingerprint in sample_fingerprints.items():
            await TrackModelFactory.create_async(
                user_id=user.id,
                provider=MusicProvider.SPOTIFY,
                provider_id=provider_id,
                fingerprint=fingerprint,
                played_at_last=old_played_at,
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
                TrackModel.fingerprint.in_(list(sample_fingerprints.values())),
            )
        )
        tracks_by_provider_id = {t.provider_id: t for t in results.scalars().all()}
        for track_id, expected in expected_played_at.items():
            assert tracks_by_provider_id[track_id].played_at_last == expected, f"Wrong played_at_last for {track_id}"

    async def test__played_count__not_doubled_on_reimport(
        self,
        async_session_db: AsyncSession,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
    ) -> None:
        config = StreamingHistoryImportConfigInput(directory=REIMPORT_HISTORY_DIR, min_ms_played=0)
        reimport_fp = "reimport track|reimport artist"
        stmt = select(TrackModel).where(
            TrackModel.user_id == user.id,
            TrackModel.fingerprint == reimport_fp,
        )

        first_report = await use_case.import_history(user=user, config=config)
        assert first_report.tracks_created == 1
        track_db = (await async_session_db.execute(stmt)).scalar_one()
        assert track_db.played_count == 3

        second_report = await use_case.import_history(user=user, config=config)
        assert second_report.tracks_played_at_updated == 1
        assert second_report.tracks_created == 0
        track_db = (await async_session_db.execute(stmt)).scalar_one()
        assert track_db.played_count == 3

    async def test__same_fingerprint__different_provider_ids__deduplicates(
        self,
        async_session_db: AsyncSession,
        user: User,
        use_case: ImportStreamingHistoryUseCase,
        tmp_path: Path,
        spotify_streaming_history: SpotifyStreamingHistoryAdapter,
    ) -> None:
        """Two Spotify IDs for the same song collapse into one DB row with merged play count."""
        import json

        history_file = tmp_path / "history.json"
        history_file.write_text(
            json.dumps(
                [
                    {
                        "ts": "2024-01-01T10:00:00Z",
                        "ms_played": 200000,
                        "master_metadata_track_name": "Duplicate Song",
                        "master_metadata_album_artist_name": "Duplicate Artist",
                        "master_metadata_album_album_name": "Album A",
                        "spotify_track_uri": "spotify:track:single_version",
                    },
                    {
                        "ts": "2024-01-02T10:00:00Z",
                        "ms_played": 200000,
                        "master_metadata_track_name": "Duplicate Song",
                        "master_metadata_album_artist_name": "Duplicate Artist",
                        "master_metadata_album_album_name": "Album B",
                        "spotify_track_uri": "spotify:track:album_version",
                    },
                ]
            )
        )

        dup_use_case = ImportStreamingHistoryUseCase(
            track_repository=use_case._track_repository,
            streaming_history=spotify_streaming_history,
        )

        report = await dup_use_case.import_history(
            user=user,
            config=StreamingHistoryImportConfigInput(directory=tmp_path, min_ms_played=0),
        )

        assert report.unique_track_ids == 1
        assert report.tracks_created == 1
        assert report.plays_total == 2

        fp = "duplicate song|duplicate artist"
        results = await async_session_db.execute(
            select(TrackModel).where(TrackModel.user_id == user.id, TrackModel.fingerprint == fp)
        )
        rows = results.scalars().all()
        assert len(rows) == 1
        assert rows[0].played_count == 2
