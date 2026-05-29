from dataclasses import dataclass
from dataclasses import field

from museflow.domain.entities.blacklist import BlacklistedArtist
from museflow.domain.entities.blacklist import BlacklistedTrack


@dataclass(frozen=True, kw_only=True)
class UserBlacklist:
    artists: list[BlacklistedArtist] = field(default_factory=list)
    tracks: list[BlacklistedTrack] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.artists and not self.tracks

    @property
    def artist_names(self) -> list[str]:
        return [a.artist_name for a in self.artists]

    @property
    def artist_fingerprints(self) -> set[str]:
        return {a.fingerprint for a in self.artists}

    @property
    def track_fingerprints(self) -> set[str]:
        return {t.fingerprint for t in self.tracks}

    @property
    def track_display_strings(self) -> list[str]:
        return [f"{t.name} by {t.artist_name}" for t in self.tracks]
