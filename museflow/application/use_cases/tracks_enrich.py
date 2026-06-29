import dataclasses
import logging
from dataclasses import dataclass

from museflow.application.inputs.enricher import EnrichTracksConfigInput
from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.repositories.track import TrackRepository
from museflow.domain.entities.user import User
from museflow.domain.utils.genre import deduplicate_genre_dict
from museflow.domain.utils.genre import normalize_genre_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EnrichTracksReport:
    enriched_count: int
    error_count: int


async def tracks_enrich(
    user: User,
    config: EnrichTracksConfigInput,
    track_repository: TrackRepository,
    track_enricher: TrackEnricherPort,
) -> EnrichTracksReport:
    tracks = await track_repository.get_list(
        user_id=user.id,
        unenriched_only=not config.force,
        limit=config.limit,
    )

    if not tracks:
        return EnrichTracksReport(enriched_count=0, error_count=0)

    batches = [tracks[i : i + config.batch_size] for i in range(0, len(tracks), config.batch_size)]
    total_batches = len(batches)
    enriched_count = 0
    error_count = 0

    for i, batch in enumerate(batches, start=1):
        try:
            enrichments = await track_enricher.enrich_tracks(batch)
        except Exception:
            logger.exception(
                f"Enrichment batch {i}/{total_batches} failed", extra={"batch": i, "total": total_batches}
            )
            error_count += 1
            continue

        enrichment_by_id = {e.track_id: e for e in enrichments}
        enriched_tracks = []
        for track in batch:
            if track.id in enrichment_by_id:
                e = enrichment_by_id[track.id]
                normalized_genres = list(
                    deduplicate_genre_dict({normalize_genre_key(g): 1.0 for g in e.genres}).keys()
                )
                enriched_tracks.append(dataclasses.replace(track, genres=normalized_genres, moods=e.moods))

        await track_repository.bulk_update(enriched_tracks, fields={"genres", "moods"})
        enriched_count += len(batch)
        logger.info(
            f"Enriched batch {i}/{total_batches} ({len(batch)} tracks)",
            extra={"batch": i, "total": total_batches, "count": len(batch)},
        )

    return EnrichTracksReport(enriched_count=enriched_count, error_count=error_count)
