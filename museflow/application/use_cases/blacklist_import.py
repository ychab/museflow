import uuid
from dataclasses import dataclass

from museflow.application.inputs.blacklist import BlacklistImportInput
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.utils.text import generate_fingerprint
from museflow.domain.utils.text import normalize_text


@dataclass(frozen=True, kw_only=True)
class ImportBlacklistResult:
    imported_artists_count: int
    imported_tracks_count: int
    skipped_count: int


async def import_blacklist(
    user_id: uuid.UUID,
    blacklist_in: BlacklistImportInput,
    uow: UnitOfWorkPort,
) -> ImportBlacklistResult:
    imported_artists_count = 0
    imported_tracks_count = 0
    skipped_count = 0

    # One block: the import is saved as a whole, or not at all.
    async with uow:
        blacklist = await uow.blacklist.get(user_id=user_id)
        # Entries already blacklisted (or repeated in the file) are kept as they are: the import is idempotent.
        artist_fingerprints = blacklist.artist_fingerprints
        track_fingerprints = blacklist.track_fingerprints

        for artist_in in blacklist_in.artists:
            fingerprint = normalize_text(artist_in.artist_name)
            if fingerprint in artist_fingerprints:
                skipped_count += 1
                continue
            await uow.blacklist.add_artist(user_id=user_id, artist_name=artist_in.artist_name)
            artist_fingerprints.add(fingerprint)
            imported_artists_count += 1

        for track_in in blacklist_in.tracks:
            fingerprint = generate_fingerprint(track_in.name, [track_in.artist_name])
            if fingerprint in track_fingerprints:
                skipped_count += 1
                continue
            await uow.blacklist.add_track(user_id=user_id, name=track_in.name, artist_name=track_in.artist_name)
            track_fingerprints.add(fingerprint)
            imported_tracks_count += 1

    return ImportBlacklistResult(
        imported_artists_count=imported_artists_count,
        imported_tracks_count=imported_tracks_count,
        skipped_count=skipped_count,
    )
