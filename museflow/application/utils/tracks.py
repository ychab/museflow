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
    not_found: list[EntryT] = field(default_factory=list)

    @property
    def not_found_count(self) -> int:
        return len(self.not_found)


def match_fingerprints[EntryT: FingerprintEntry](
    entries: Iterable[EntryT],
    tracks: Iterable[Track],
) -> FingerprintMatches[EntryT]:
    """Pairs each entry with the track of the same fingerprint, collecting the entries that match none."""
    fingerprint_to_track = {track.fingerprint: track for track in tracks}

    matched: list[tuple[EntryT, Track]] = []
    not_found: list[EntryT] = []
    for entry in entries:
        track = fingerprint_to_track.get(entry.fingerprint)
        if track is None:
            not_found.append(entry)
        else:
            matched.append((entry, track))

    return FingerprintMatches(matched=matched, not_found=not_found)
