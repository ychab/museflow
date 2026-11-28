import dataclasses
import logging
import uuid
from dataclasses import dataclass

from museflow.application.inputs.enrich import EnrichTracksConfigInput
from museflow.application.outputs.progress import StepAdvanced
from museflow.application.outputs.progress import StepDone
from museflow.application.outputs.progress import StepStarted
from museflow.application.ports.enrichers.track import TrackEnricherPort
from museflow.application.ports.progress import ProgressPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.services.llm_usage import LLMUsageService
from museflow.domain.entities.track import Track
from museflow.domain.entities.user import User
from museflow.domain.enums import EnrichField
from museflow.domain.enums import LLMOperation
from museflow.domain.enums import ProgressStep
from museflow.domain.exceptions import EnricherRateLimitExceededError
from museflow.domain.exceptions import EnricherUnavailableError
from museflow.domain.exceptions import TrackEnrichmentAbortedError
from museflow.domain.exceptions import TrackEnrichmentError
from museflow.domain.value_objects.track import TrackEnrichment

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EnrichTracksReport:
    enriched_count: int
    error_count: int
    not_found_count: int = 0  # fingerprints asked for that match none of the user's tracks


class EnrichTracksUseCase:
    def __init__(
        self,
        uow: UnitOfWorkPort,
        track_enricher: TrackEnricherPort,
        progress: ProgressPort,
    ) -> None:
        self._uow = uow
        self._track_enricher = track_enricher
        self._progress = progress
        self._llm_usage = LLMUsageService(uow=uow)

    async def enrich(self, user: User, config: EnrichTracksConfigInput) -> EnrichTracksReport:
        """Enriches the user's tracks batch by batch; each batch is saved at once with its cost, so a stop keeps both.

        Raises:
            TrackEnrichmentAbortedError: If the enricher cannot serve any batch (auth, credits, outage, rate
                limit), or after `max_consecutive_failures` failed batches in a row, since a failed batch may still be
                billed.
        """
        run_id = uuid.uuid4()

        # What the enricher spent since its last batch is saved whatever the outcome: an aborted run was billed too.
        try:
            report = await self._enrich(user, config, run_id)
        finally:
            await self._llm_usage.save(
                user_id=user.id,
                run_id=run_id,
                operation=LLMOperation.ENRICH,
                usages=self._track_enricher.pop_usages(),
            )
        return report

    async def _enrich(self, user: User, config: EnrichTracksConfigInput, run_id: uuid.UUID) -> EnrichTracksReport:
        missing_fields = None if config.force else config.fields
        not_found_count = 0

        async with self._uow as uow:
            tracks = await uow.tracks.get_list(
                user_id=user.id,
                fingerprints=config.fingerprints,
                missing_fields=missing_fields,
                limit=config.limit,
            )
            if config.fingerprints is not None:
                known = await uow.tracks.get_known_identifiers(user.id, config.fingerprints)
                not_found_count = len(set(config.fingerprints) - known.fingerprints)

        if not tracks:
            return EnrichTracksReport(enriched_count=0, error_count=0, not_found_count=not_found_count)

        batches = [tracks[i : i + config.batch_size] for i in range(0, len(tracks), config.batch_size)]
        total_batches = len(batches)
        enriched_count = error_count = consecutive_failures = tracks_done = 0
        last_failure = ""

        await self._progress.publish(StepStarted(step=ProgressStep.ENRICH_TRACKS, total=len(tracks)))

        for i, batch in enumerate(batches, start=1):
            try:
                enrichments = await self._track_enricher.enrich_tracks(batch, fields=config.fields)
            except (EnricherRateLimitExceededError, EnricherUnavailableError) as e:
                raise TrackEnrichmentAbortedError(i, total_batches, enriched_count, reason=str(e)) from e
            except TrackEnrichmentError as e:
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

            tracks_done += len(batch)
            # Paid even when it failed: a batch saves its cost at once, with its tracks or alone, so a process killed
            # later in the run keeps it.
            usages = self._track_enricher.pop_usages()

            await self._progress.publish(
                StepAdvanced(step=ProgressStep.ENRICH_TRACKS, done=tracks_done, total=len(tracks))
            )

            if not enriched_tracks:
                async with self._uow as uow:
                    await self._llm_usage.add(user.id, run_id, LLMOperation.ENRICH, usages, uow=uow)

                error_count += 1
                consecutive_failures += 1

                if consecutive_failures >= config.max_consecutive_failures:
                    raise TrackEnrichmentAbortedError(
                        i,
                        total_batches,
                        enriched_count,
                        reason=f"{consecutive_failures} batches failed in a row (last: {last_failure})",
                    )
                continue
            consecutive_failures = 0

            # One block per batch: a paid batch survives a later failure, and a run that resumes skips its tracks.
            # Accepted risk: this write failing (the database unreachable), or the process dying before it, loses the
            # batch and its cost, which the next try pays again; one batch at most.
            async with self._uow as uow:
                await uow.tracks.bulk_update(enriched_tracks, fields=config.fields)
                await self._llm_usage.add(user.id, run_id, LLMOperation.ENRICH, usages, uow=uow)

            enriched_count += len(enriched_tracks)

            # Left out by the model or with no usable answer: those tracks stay eligible for the next run
            if skipped := len(batch) - len(enriched_tracks):
                logger.warning(
                    f"Enrichment batch {i}/{total_batches}: {skipped} track(s) skipped, left for the next run",
                    extra={"batch": i, "total": total_batches, "skipped": skipped},
                )

        await self._progress.publish(StepDone(step=ProgressStep.ENRICH_TRACKS))

        return EnrichTracksReport(
            enriched_count=enriched_count,
            error_count=error_count,
            not_found_count=not_found_count,
        )

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
                    logger.warning(
                        f"Enrichment returned no genres for {str(track)!r}", extra={"track_id": str(track.id)}
                    )

            if EnrichField.MOOD in fields:
                if enrichment.moods:
                    enriched = dataclasses.replace(enriched, moods=enrichment.moods)
                else:
                    logger.warning(
                        f"Enrichment returned no moods for {str(track)!r}", extra={"track_id": str(track.id)}
                    )

            # An empty locales list is an answer (no sung language); None means no usable answer.
            if EnrichField.LOCALE in fields and enrichment.locales is not None:
                enriched = dataclasses.replace(enriched, locales=enrichment.locales)

            if enriched is not track:
                enriched_tracks.append(enriched)

        return enriched_tracks
