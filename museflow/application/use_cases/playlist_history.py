from datetime import UTC
from datetime import datetime

from museflow import __project_name__
from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.ports.repositories.track import TrackRepository
from museflow.domain.entities.playlist import Playlist
from museflow.domain.entities.user import User
from museflow.domain.exceptions import PlaylistNoTracksError
from museflow.domain.types import PlaylistType
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy
from museflow.domain.types import TrackSource


async def playlist_history(
    user: User,
    config: PlaylistHistoryConfigInput,
    track_repository: TrackRepository,
    playlist_repository: PlaylistRepository,
    provider_library: ProviderLibraryPort,
) -> Playlist:
    exclude_ids = None
    if not config.allow_duplicate:
        exclude_ids = list(await playlist_repository.get_track_ids(user.id, type=PlaylistType.HISTORY))

    tracks = await track_repository.get_list(
        user_id=user.id,
        source=TrackSource.HISTORY,
        min_score=config.score_min,
        max_score=config.score_max,
        artist_name=config.artist_name,
        exclude_ids=exclude_ids,
        order=[(TrackOrderBy.PLAYED_COUNT, SortOrder.DESC)],
        limit=config.limit,
    )
    if not tracks:
        raise PlaylistNoTracksError()

    playlist = await provider_library.create_playlist(
        name=f"[{__project_name__.capitalize()}] - History - {datetime.now(UTC).isoformat()}",
        type=PlaylistType.HISTORY,
        tracks=tracks,
    )
    return await playlist_repository.save(playlist)
