import dataclasses
import uuid
from dataclasses import dataclass

from museflow.application.inputs.enrich import EnrichEntryInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.utils.tracks import match_fingerprints
from museflow.domain.enums import EnrichField


@dataclass(frozen=True, kw_only=True)
class EnrichmentImportResult:
    imported_count: int
    not_found_count: int


async def import_enrichment(
    user_id: uuid.UUID,
    entries: list[EnrichEntryInput],
    uow: UnitOfWorkPort,
) -> EnrichmentImportResult:
    # One block: the import is saved as a whole, or not at all.
    async with uow:
        matches = match_fingerprints(entries, await uow.tracks.get_list(user_id=user_id))
        updated_tracks = [
            dataclasses.replace(track, genres=entry.genres, moods=entry.moods, locales=entry.locales)
            for entry, track in matches.matched
        ]
        if updated_tracks:
            await uow.tracks.bulk_update(updated_tracks, fields=frozenset(EnrichField))

    return EnrichmentImportResult(imported_count=len(updated_tracks), not_found_count=matches.not_found_count)
