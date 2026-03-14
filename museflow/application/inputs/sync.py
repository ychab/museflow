from dataclasses import dataclass


@dataclass(frozen=True)
class SyncConfigInput:
    """Configuration for a library synchronization operation.

    This dataclass specifies which types of data (artists, tracks, etc.) should be
    purged or synchronized, along with pagination and time range settings.
    """

    purge_all: bool = False
    purge_artist_top: bool = False
    purge_track_top: bool = False
    purge_track_saved: bool = False
    purge_track_playlist: bool = False
    sync_all: bool = False
    sync_artist_top: bool = False
    sync_track_top: bool = False
    sync_track_saved: bool = False
    sync_track_playlist: bool = False
    page_size: int = 50
    time_range: str | None = None
    batch_size: int = 300

    def has_purge(self) -> bool:
        return any(
            [
                self.purge_all,
                self.purge_artist_top,
                self.purge_track_top,
                self.purge_track_saved,
                self.purge_track_playlist,
            ],
        )

    def has_sync(self) -> bool:
        return any(
            [
                self.sync_all,
                self.sync_artist_top,
                self.sync_track_top,
                self.sync_track_saved,
                self.sync_track_playlist,
            ]
        )
