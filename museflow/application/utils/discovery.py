import logging
from collections import Counter
from dataclasses import dataclass

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.application.ports.repositories.music import TrackRepository
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.entities.user import User
from museflow.domain.services.reconciler import TrackReconciler
from museflow.domain.types import ScoreAdvisor
from museflow.domain.types import ScoreReconciler

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class TrackScored:
    track: Track
    advisor_score: ScoreAdvisor
    reconciler_score: ScoreReconciler


async def reconcile_tracks(
    tracks_suggested: list[TrackSuggested],
    limit: int,
    provider_library: ProviderLibraryPort,
    track_reconciler: TrackReconciler,
) -> list[TrackScored]:
    tracks_reconciled: list[TrackScored] = []

    for track_suggested in tracks_suggested:
        candidates = await provider_library.search_tracks(
            track=track_suggested.name,
            artists=track_suggested.artists,
            page_size=limit,
            log_enabled=False,
        )

        result = track_reconciler.reconcile(
            track_suggested=track_suggested,
            candidates=candidates,
        )
        if result:
            best_match, reconciler_score = result
            tracks_reconciled.append(
                TrackScored(
                    track=best_match,
                    advisor_score=track_suggested.score,
                    reconciler_score=reconciler_score,
                )
            )
            logger.debug(f"Track reconciled: '{track_suggested}'")
        else:
            logger.debug(f"Track not reconciled: '{track_suggested}'")

    return tracks_reconciled


async def filter_known_tracks(
    user: User,
    tracks_scored: list[TrackScored],
    track_repository: TrackRepository,
) -> list[TrackScored]:
    known_identifiers = await track_repository.get_known_identifiers(
        user_id=user.id,
        isrcs=[ts.track.isrc for ts in tracks_scored if ts.track.isrc],
        fingerprints=[ts.track.fingerprint for ts in tracks_scored],
    )

    result: list[TrackScored] = []
    for ts in tracks_scored:
        if known_identifiers.is_known(ts.track):
            logger.debug(f"Excluded '{ts.track}'")
            continue
        result.append(ts)

    return result


def apply_artist_cap(tracks: list[Track], max_tracks_per_artist: int) -> list[Track]:
    tracks_filtered: list[Track] = []
    artist_counts: Counter[str] = Counter()

    for track in tracks:
        artist_provider_id = track.artists[0].provider_id
        if artist_counts[artist_provider_id] < max_tracks_per_artist:
            tracks_filtered.append(track)
            artist_counts[artist_provider_id] += 1

    return tracks_filtered
