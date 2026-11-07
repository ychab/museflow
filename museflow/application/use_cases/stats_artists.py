import math
import uuid
from collections import defaultdict
from typing import cast

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track
from museflow.domain.enums import ArtistSortBy
from museflow.domain.enums import SourceFilter
from museflow.domain.value_objects.stats import ArtistStats


def _is_in_score_range(score: int | None, score_min: int | None, score_max: int | None) -> bool:
    if score is None:
        return False
    if score_min is not None and score < score_min:
        return False
    if score_max is not None and score > score_max:
        return False
    return True


async def get_top_artists(
    user_id: uuid.UUID,
    source: SourceFilter,
    score_min: int | None,
    score_max: int | None,
    confidence: int,
    sort: ArtistSortBy,
    limit: int,
    uow: UnitOfWorkPort,
) -> list[ArtistStats]:
    async with uow:
        all_tracks = await uow.tracks.get_list(
            user_id=user_id,
            source=source.to_track_source(),
            limit=None,
        )

    artist_tracks: dict[str, list[Track]] = defaultdict(list)
    for track in all_tracks:
        artist_tracks[track.primary_artist].append(track)

    all_rated_scores = [cast(int, t.score) for t in all_tracks if _is_in_score_range(t.score, score_min, score_max)]
    global_mean = sum(all_rated_scores) / len(all_rated_scores) if all_rated_scores else 0.0

    rows: list[ArtistStats] = []
    for artist, tracks in artist_tracks.items():
        rated_scores = [cast(int, t.score) for t in tracks if _is_in_score_range(t.score, score_min, score_max)]
        rated_count = len(rated_scores)
        track_count = len(tracks)
        plays_count = sum(t.played_count for t in tracks)

        rate_avg: float | None
        quality_score: float | None
        if rated_count > 0:
            rate_avg = sum(rated_scores) / rated_count
            quality = (confidence * global_mean + rated_count * rate_avg) / (confidence + rated_count)
            quality_score = quality
        else:
            rate_avg = None
            quality = global_mean
            quality_score = None

        quality_ratio = quality / global_mean if global_mean > 0 else 1.0
        overall_score = math.log(1 + track_count) * math.log(1 + plays_count) * quality_ratio

        rows.append(
            ArtistStats(
                artist=artist,
                quality_score=quality_score,
                overall_score=overall_score,
                rate_avg=rate_avg,
                rated_count=rated_count,
                track_count=track_count,
                plays_count=plays_count,
            )
        )

    if sort == ArtistSortBy.TRACK_COUNT:
        rows.sort(key=lambda r: (-r.track_count, r.artist))
    elif sort == ArtistSortBy.PLAYS_COUNT:
        rows.sort(key=lambda r: (-r.plays_count, r.artist))
    elif sort == ArtistSortBy.RATE_AVG:
        rows.sort(key=lambda r: (-(r.rate_avg or 0.0), r.artist))
    elif sort == ArtistSortBy.QUALITY:
        rows.sort(key=lambda r: (-(r.quality_score or 0.0), r.artist))
    else:
        rows.sort(key=lambda r: (-r.overall_score, r.artist))

    return rows[:limit]
