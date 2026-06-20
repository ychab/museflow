from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Final

import pytest

from museflow.domain.exceptions import StreamingHistoryInvalidFormat
from museflow.infrastructure.adapters.providers.spotify.history import SpotifyStreamingHistoryAdapter

from tests import ASSETS_DIR

HISTORY_SCENARIOS: Final[Path] = ASSETS_DIR / "history" / "spotify" / "scenarios"


class TestSpotifyStreamingHistoryAdapter:
    @pytest.fixture
    def adapter(self) -> SpotifyStreamingHistoryAdapter:
        return SpotifyStreamingHistoryAdapter()

    async def test__parse_file__nominal(self, adapter: SpotifyStreamingHistoryAdapter) -> None:
        entries, stats = await adapter.parse_file(
            path=HISTORY_SCENARIOS / "valid_single_track.json", min_ms_played=30_000
        )

        assert len(entries) == 1
        assert entries[0].provider_id == "abc123"
        assert entries[0].name == "Song Name"
        assert entries[0].artist == "Artist Name"
        assert entries[0].album_name == "Album Name"
        assert stats.items_read == 1
        assert stats.items_skipped_no_timestamp == 0
        assert stats.items_skipped_short_play == 0
        assert stats.items_skipped_no_track_id == 0

    async def test__parse_file__filter__no_timestamp(self, adapter: SpotifyStreamingHistoryAdapter) -> None:
        entries, stats = await adapter.parse_file(path=HISTORY_SCENARIOS / "skips_no_timestamp.json", min_ms_played=0)

        assert len(entries) == 1
        assert stats.items_read == 3
        assert stats.items_skipped_no_timestamp == 2

    async def test__parse_file__filter__short_play(self, adapter: SpotifyStreamingHistoryAdapter) -> None:
        entries, stats = await adapter.parse_file(
            path=HISTORY_SCENARIOS / "skips_short_play.json", min_ms_played=30_000
        )

        assert len(entries) == 1
        assert stats.items_read == 3
        assert stats.items_skipped_short_play == 2

    async def test__parse_file__filter__no_track_id(self, adapter: SpotifyStreamingHistoryAdapter) -> None:
        entries, stats = await adapter.parse_file(path=HISTORY_SCENARIOS / "skips_no_track_id.json", min_ms_played=0)

        assert len(entries) == 1
        assert stats.items_read == 3
        assert stats.items_skipped_no_track_id == 2

    async def test__parse_file__filter__non_track_uri(self, adapter: SpotifyStreamingHistoryAdapter) -> None:
        entries, stats = await adapter.parse_file(path=HISTORY_SCENARIOS / "skips_invalid_uri.json", min_ms_played=0)

        assert len(entries) == 1
        assert entries[0].provider_id == "real_track_id"
        assert stats.items_skipped_no_track_id == 2

    async def test__parse_file__duplicate_tracks_all_kept(self, adapter: SpotifyStreamingHistoryAdapter) -> None:
        entries, stats = await adapter.parse_file(path=HISTORY_SCENARIOS / "duplicate_track_ids.json", min_ms_played=0)

        assert len(entries) == 3
        assert all(entry.provider_id == "dup1" for entry in entries)
        assert {entry.played_at for entry in entries} == {
            datetime(2023, 1, 2, 10, 0, 0, tzinfo=UTC),
            datetime(2023, 1, 3, 10, 0, 0, tzinfo=UTC),
            datetime(2023, 1, 1, 10, 0, 0, tzinfo=UTC),
        }
        assert stats.items_read == 3

    async def test__parse_file__invalid_json(self, adapter: SpotifyStreamingHistoryAdapter, tmp_path: Path) -> None:
        path = tmp_path / "history.json"
        path.write_text("{invalid json")

        with pytest.raises(StreamingHistoryInvalidFormat):
            await adapter.parse_file(path=path, min_ms_played=0)
