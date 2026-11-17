import uuid
from dataclasses import dataclass

from museflow.application.inputs.rate import RatingEntryInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.utils.tracks import match_fingerprints
from museflow.domain.entities.track import Track


@dataclass(frozen=True, kw_only=True)
class ImportRatingsResult:
    imported_count: int
    skipped_count: int
    created_count: int
    not_found_count: int


async def import_ratings(
    user_id: uuid.UUID,
    entries: list[RatingEntryInput],
    uow: UnitOfWorkPort,
) -> ImportRatingsResult:
    imported_count = 0
    skipped_count = 0

    # One block: the import is saved as a whole, or not at all.
    async with uow:
        matches = match_fingerprints(entries, await uow.tracks.get_list(user_id=user_id))
        entry_track_ids = [(entry, track.id) for entry, track in matches.matched]

        # Recreate the tracks the library lacks (e.g. a rated discovery never played, after a reset)
        tracks_missing = [track for entry in matches.not_found if (track := _to_track(user_id, entry)) is not None]
        track_ids, created_count = await uow.tracks.bulk_upsert(tracks_missing, batch_size=100)
        entry_track_ids += [
            (entry, track_ids[entry.fingerprint]) for entry in matches.not_found if entry.fingerprint in track_ids
        ]

        for entry, track_id in entry_track_ids:
            if entry.score_skipped:
                await uow.tracks.skip(user_id=user_id, track_id=track_id)
                skipped_count += 1
            elif entry.score is not None:
                await uow.tracks.rate(user_id=user_id, track_id=track_id, score=entry.score)
                imported_count += 1

    return ImportRatingsResult(
        imported_count=imported_count,
        skipped_count=skipped_count,
        created_count=created_count,
        not_found_count=matches.not_found_count - len(track_ids),
    )


def _to_track(user_id: uuid.UUID, entry: RatingEntryInput) -> Track | None:
    # An entry exported before the track data was added only rates a track already in the library
    if not entry.name or not entry.artists or not entry.provider_links:
        return None

    return Track(
        user_id=user_id,
        name=entry.name,
        artists=entry.artists,
        album_name=entry.album_name,
        fingerprint=entry.fingerprint,
        provider_links=entry.provider_links,
        source=entry.source,
    )
