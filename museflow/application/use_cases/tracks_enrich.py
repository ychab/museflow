import dataclasses
import logging
from dataclasses import dataclass

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.repositories.track import TrackRepository
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField

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
    missing_fields = None if config.force else config.fields

    tracks = await track_repository.get_list(
        user_id=user.id,
        missing_fields=missing_fields,
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
            enrichments = await track_enricher.enrich_tracks(batch, fields=config.fields)
        except Exception:
            logger.exception(
                f"Enrichment batch {i}/{total_batches} failed", extra={"batch": i, "total": total_batches}
            )
            error_count += 1
            continue

        enrichment_by_id = {e.track_id: e for e in enrichments}
        enriched_tracks = []
        for track in batch:
            if track.id not in enrichment_by_id:
                continue
            enrichment = enrichment_by_id[track.id]
            enriched = track

            # Genres and moods are mandatory: an empty answer is a failure, so the track stays eligible.
            if EnrichField.GENRE in config.fields:
                if enrichment.genres:
                    enriched = dataclasses.replace(enriched, genres=enrichment.genres)
                else:
                    logger.warning("Enrichment returned no genres", extra={"track_id": str(track.id)})
            if EnrichField.MOOD in config.fields:
                if enrichment.moods:
                    enriched = dataclasses.replace(enriched, moods=enrichment.moods)
                else:
                    logger.warning("Enrichment returned no moods", extra={"track_id": str(track.id)})
            # An empty locales list is an answer (no sung language); None means no usable answer.
            if EnrichField.LOCALE in config.fields and enrichment.locales is not None:
                enriched = dataclasses.replace(enriched, locales=enrichment.locales)

            if enriched is not track:
                enriched_tracks.append(enriched)

        if not enriched_tracks:
            logger.warning(
                f"Enrichment batch {i}/{total_batches} returned no enrichment",
                extra={"batch": i, "total": total_batches},
            )
            error_count += 1
            continue

        await track_repository.bulk_update(enriched_tracks, fields=config.fields)
        enriched_count += len(enriched_tracks)
        logger.info(
            f"Enriched batch {i}/{total_batches} ({len(enriched_tracks)}/{len(batch)} tracks)",
            extra={"batch": i, "total": total_batches, "count": len(enriched_tracks)},
        )

    return EnrichTracksReport(enriched_count=enriched_count, error_count=error_count)
