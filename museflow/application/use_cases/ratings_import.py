import uuid
from dataclasses import dataclass

from museflow.application.inputs.rate import RateEntryInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.utils.tracks import match_fingerprints


@dataclass(frozen=True, kw_only=True)
class RatingsImportResult:
    imported_count: int
    skipped_count: int
    not_found_count: int


async def import_ratings(
    user_id: uuid.UUID,
    entries: list[RateEntryInput],
    uow: UnitOfWorkPort,
) -> RatingsImportResult:
    imported_count = 0
    skipped_count = 0

    # One block: the import is saved as a whole, or not at all.
    async with uow:
        matches = match_fingerprints(entries, await uow.tracks.get_list(user_id=user_id))
        for entry, track in matches.matched:
            if entry.score_skipped:
                await uow.tracks.skip(user_id=user_id, track_id=track.id)
                skipped_count += 1
            elif entry.score is not None:
                await uow.tracks.rate(user_id=user_id, track_id=track.id, score=entry.score)
                imported_count += 1

    return RatingsImportResult(
        imported_count=imported_count,
        skipped_count=skipped_count,
        not_found_count=matches.not_found_count,
    )
