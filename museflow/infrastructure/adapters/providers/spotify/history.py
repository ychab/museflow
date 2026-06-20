import asyncio
import logging
from datetime import datetime
from pathlib import Path

import ijson

from museflow.application.inputs.history import StreamingHistoryEntry
from museflow.application.inputs.history import StreamingHistoryFileStats
from museflow.application.ports.providers.history import StreamingHistoryPort
from museflow.domain.exceptions import StreamingHistoryInvalidFormat

logger = logging.getLogger(__name__)


class SpotifyStreamingHistoryAdapter(StreamingHistoryPort):
    async def parse_file(
        self,
        path: Path,
        min_ms_played: int,
    ) -> tuple[list[StreamingHistoryEntry], StreamingHistoryFileStats]:
        return await asyncio.to_thread(
            self._parse_file_sync,
            path=path,
            min_ms_played=min_ms_played,
        )

    @staticmethod
    def _parse_file_sync(
        path: Path, min_ms_played: int
    ) -> tuple[list[StreamingHistoryEntry], StreamingHistoryFileStats]:
        track_entries: list[StreamingHistoryEntry] = []

        items_read = 0
        items_skipped_no_timestamp = 0
        items_skipped_short_play = 0
        items_skipped_no_track_id = 0

        try:
            with open(path, "rb") as f:
                for item in ijson.items(f, "item"):
                    items_read += 1

                    ts_raw = item.get("ts")
                    if not ts_raw:
                        items_skipped_no_timestamp += 1
                        continue
                    ts = datetime.fromisoformat(ts_raw)

                    if item.get("ms_played", 0) < min_ms_played:
                        items_skipped_short_play += 1
                        continue

                    uri = item.get("spotify_track_uri")
                    name = item.get("master_metadata_track_name")
                    if uri is None or not name:
                        items_skipped_no_track_id += 1
                        continue

                    parts = uri.split(":")
                    if len(parts) != 3 or parts[1] != "track":
                        items_skipped_no_track_id += 1
                        continue

                    track_id = parts[2]
                    artist = item.get("master_metadata_album_artist_name") or ""
                    album_name = item.get("master_metadata_album_album_name") or None

                    track_entries.append(
                        StreamingHistoryEntry(
                            provider_id=track_id,
                            played_at=ts,
                            name=name,
                            artist=artist,
                            album_name=album_name,
                        )
                    )
        except Exception as exc:
            raise StreamingHistoryInvalidFormat(f"Failed to parse {path}: {exc}") from exc

        return track_entries, StreamingHistoryFileStats(
            items_read=items_read,
            items_skipped_no_timestamp=items_skipped_no_timestamp,
            items_skipped_short_play=items_skipped_short_play,
            items_skipped_no_track_id=items_skipped_no_track_id,
        )
