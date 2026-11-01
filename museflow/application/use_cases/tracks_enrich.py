import dataclasses
import logging
from dataclasses import dataclass

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.exceptions import EnricherRateLimitExceeded
from museflow.domain.exceptions import EnricherUnavailableException
from museflow.domain.exceptions import TrackEnrichmentAbortedException
from museflow.domain.exceptions import TrackEnrichmentException
from museflow.domain.value_objects.track import TrackEnrichment

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EnrichTracksReport:
    enriched_count: int
    error_count: int


class EnrichTracksUseCase:
    def __init__(
        self,
        uow: UnitOfWorkPort,
        track_enricher: TrackEnricherPort,
    ) -> None:
        self._uow = uow
        self._track_enricher = track_enricher

    async def enrich(self, user: User, config: EnrichTracksConfigInput) -> EnrichTracksReport:
        """Enriches the user's tracks batch by batch; each enriched batch is saved at once, so a stop keeps it.

        Raises:
            TrackEnrichmentAbortedException: If the enricher cannot serve any batch (auth, credits, outage, rate
                limit), or after `max_consecutive_failures` failed batches in a row, since a failed batch may still be
                billed.
        """
        missing_fields = None if config.force else config.fields

        async with self._uow as uow:
            tracks = await uow.tracks.get_list(
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
        consecutive_failures = 0
        last_failure = ""

        for i, batch in enumerate(batches, start=1):
            try:
                enrichments = await self._track_enricher.enrich_tracks(batch, fields=config.fields)
            except (EnricherRateLimitExceeded, EnricherUnavailableException) as e:
                raise TrackEnrichmentAbortedException(i, total_batches, enriched_count, reason=str(e)) from e
            except TrackEnrichmentException as e:
                # An expected batch failure, already explained by its message: no traceback
                logger.warning(
                    f"Enrichment batch {i}/{total_batches} failed: {e}", extra={"batch": i, "total": total_batches}
                )
                enriched_tracks: list[Track] = []
                last_failure = str(e)
            except Exception as e:
                logger.exception(
                    f"Enrichment batch {i}/{total_batches} failed", extra={"batch": i, "total": total_batches}
                )
                enriched_tracks = []
                last_failure = repr(e)
            else:
                enriched_tracks = self._apply_enrichments(batch, enrichments, config.fields)
                if not enriched_tracks:
                    logger.warning(
                        f"Enrichment batch {i}/{total_batches} returned no enrichment",
                        extra={"batch": i, "total": total_batches},
                    )
                    last_failure = "no enrichment returned"

            if not enriched_tracks:
                error_count += 1
                consecutive_failures += 1
                if consecutive_failures >= config.max_consecutive_failures:
                    raise TrackEnrichmentAbortedException(
                        i,
                        total_batches,
                        enriched_count,
                        reason=f"{consecutive_failures} batches failed in a row (last: {last_failure})",
                    )
                continue

            consecutive_failures = 0

            # One block per batch: a paid batch survives a later failure.
            async with self._uow as uow:
                await uow.tracks.bulk_update(enriched_tracks, fields=config.fields)

            enriched_count += len(enriched_tracks)
            logger.info(
                f"Enriched batch {i}/{total_batches} ({len(enriched_tracks)}/{len(batch)} tracks)",
                extra={"batch": i, "total": total_batches, "count": len(enriched_tracks)},
            )

        return EnrichTracksReport(enriched_count=enriched_count, error_count=error_count)

    def _apply_enrichments(
        self,
        batch: list[Track],
        enrichments: list[TrackEnrichment],
        fields: frozenset[EnrichField],
    ) -> list[Track]:
        enrichment_by_id = {e.track_id: e for e in enrichments}
        enriched_tracks = []
        for track in batch:
            if track.id not in enrichment_by_id:
                continue
            enrichment = enrichment_by_id[track.id]
            enriched = track

            # Genres and moods are mandatory: an empty answer is a failure, so the track stays eligible.
            if EnrichField.GENRE in fields:
                if enrichment.genres:
                    enriched = dataclasses.replace(enriched, genres=enrichment.genres)
                else:
                    logger.warning("Enrichment returned no genres", extra={"track_id": str(track.id)})
            if EnrichField.MOOD in fields:
                if enrichment.moods:
                    enriched = dataclasses.replace(enriched, moods=enrichment.moods)
                else:
                    logger.warning("Enrichment returned no moods", extra={"track_id": str(track.id)})
            # An empty locales list is an answer (no sung language); None means no usable answer.
            if EnrichField.LOCALE in fields and enrichment.locales is not None:
                enriched = dataclasses.replace(enriched, locales=enrichment.locales)

            if enriched is not track:
                enriched_tracks.append(enriched)

        return enriched_tracks
