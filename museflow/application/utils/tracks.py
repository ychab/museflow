from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from typing import Protocol

from museflow.domain.entities.track import Track


class FingerprintEntry(Protocol):
    fingerprint: str


@dataclass(frozen=True, kw_only=True)
class FingerprintMatches[EntryT: FingerprintEntry]:
    matched: list[tuple[EntryT, Track]] = field(default_factory=list)
    not_found_count: int = 0


def match_fingerprints[EntryT: FingerprintEntry](
    entries: Iterable[EntryT],
    tracks: Iterable[Track],
) -> FingerprintMatches[EntryT]:
    """Pairs each entry with the track of the same fingerprint, counting the entries that match none."""
    fingerprint_to_track = {track.fingerprint: track for track in tracks}

    matched: list[tuple[EntryT, Track]] = []
    not_found_count = 0
    for entry in entries:
        track = fingerprint_to_track.get(entry.fingerprint)
        if track is None:
            not_found_count += 1
        else:
            matched.append((entry, track))

    return FingerprintMatches(matched=matched, not_found_count=not_found_count)
