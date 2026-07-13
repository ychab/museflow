from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.ports.repositories.track import TrackRepository
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import PlaylistHistoryOrderBy
from museflow.domain.enums import PlaylistType
from museflow.domain.enums import SortOrder
from museflow.domain.enums import TrackOrderBy
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import PlaylistNoTracksError


@dataclass(frozen=True, kw_only=True)
class PlaylistHistoryResult:
    playlist: Playlist | None
    tracks: list[Track]


async def playlist_history(
    user: User,
    config: PlaylistHistoryConfigInput,
    track_repository: TrackRepository,
    playlist_repository: PlaylistRepository,
    provider_library: ProviderLibraryPort,
) -> PlaylistHistoryResult:
    exclude_ids = None
    if not config.allow_duplicate:
        exclude_ids = list(await playlist_repository.get_track_ids(user.id, type=PlaylistType.HISTORY))

    tracks = await track_repository.get_list(
        user_id=user.id,
        source=TrackSource.HISTORY,
        min_score=config.score_min,
        max_score=config.score_max,
        artist_name=config.artist_name,
        genres=config.genres or None,
        moods=config.moods or None,
        locales=config.locales or None,
        played_first_min=config.played_first_min,
        played_first_max=config.played_first_max,
        played_last_min=config.played_last_min,
        played_last_max=config.played_last_max,
        exclude_ids=exclude_ids,
        order=[(TrackOrderBy(config.sort_by.value), SortOrder.DESC)],
        limit=config.limit,
    )
    if not tracks:
        raise PlaylistNoTracksError()

    if config.group_by_artists:
        groups: dict[str, list[Track]] = defaultdict(list)
        for track in tracks:
            groups[track.primary_artist].append(track)

        def artist_sort_key(group_tracks: list[Track]) -> float:
            if config.sort_by == PlaylistHistoryOrderBy.SCORE:
                scores = [t.score for t in group_tracks if t.score is not None]
                return float(max(scores)) if scores else -1.0
            return float(max(t.played_count for t in group_tracks))

        sorted_groups = sorted(groups.values(), key=artist_sort_key, reverse=True)
        tracks = [track for group in sorted_groups for track in group]

    if config.dry_run:
        return PlaylistHistoryResult(playlist=None, tracks=tracks)

    name_prefix = "[MF] - History"
    name_suffix = (
        config.name_suffix if config.name_suffix is not None else datetime.now(UTC).isoformat(timespec="seconds")
    )

    playlist = await provider_library.create_playlist(
        name=f"{name_prefix} - {name_suffix}",
        type=PlaylistType.HISTORY,
        tracks=tracks,
    )
    playlist = await playlist_repository.save(playlist)

    return PlaylistHistoryResult(playlist=playlist, tracks=tracks)
