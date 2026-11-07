import uuid
from collections import defaultdict

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track
from museflow.domain.enums import SourceFilter
from museflow.domain.value_objects.stats import ArtistCandidate


async def get_artist_candidates(
    user_id: uuid.UUID,
    source: SourceFilter,
    max_tracks: int,
    min_avg: float,
    limit: int,
    uow: UnitOfWorkPort,
) -> list[ArtistCandidate]:
    async with uow:
        all_tracks = await uow.tracks.get_list(
            user_id=user_id,
            source=source.to_track_source(),
            limit=None,
        )

    artist_tracks: dict[str, list[Track]] = defaultdict(list)
    for track in all_tracks:
        artist_tracks[track.primary_artist].append(track)

    rows: list[ArtistCandidate] = []
    for artist, tracks in artist_tracks.items():
        total_count = len(tracks)
        if total_count > max_tracks:
            continue

        rated_scores = [t.score for t in tracks if t.score is not None]
        rated_count = len(rated_scores)
        if rated_count == 0:
            continue

        avg_score = sum(rated_scores) / rated_count
        if avg_score < min_avg:
            continue

        rows.append(
            ArtistCandidate(
                artist=artist,
                avg_score=avg_score,
                rated_count=rated_count,
                total_count=total_count,
            )
        )

    rows.sort(key=lambda r: (-r.avg_score, r.artist))
    return rows[:limit]
