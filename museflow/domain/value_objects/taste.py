from dataclasses import dataclass
from datetime import datetime

from museflow.domain.entities.track import Track
from museflow.domain.entities.track import TrackSuggested


@dataclass(frozen=True, kw_only=True)
class DiscoveryTasteStrategy:
    reasoning: str
    strategy_label: str
    recommended_tracks: list[TrackSuggested]
    suggested_playlist_name: str


@dataclass(frozen=True, kw_only=True)
class ArtistSuggested:
    name: str
    sound: str  # what the advisor wants from this artist for the request, to guide the pick among their tracks
    score: float


@dataclass(frozen=True, kw_only=True)
class DiscoveryArtistStrategy:
    reasoning: str
    strategy_label: str
    artists: list[ArtistSuggested]
    suggested_playlist_name: str


@dataclass(frozen=True, kw_only=True)
class TrackPicked:
    """A catalogue track the advisor chose among the candidates it was given."""

    track: Track
    score: float


@dataclass(frozen=True, kw_only=True)
class PeriodTrack:
    """A track as listened to during one period."""

    track: Track
    plays: int  # in the period, not over the whole history


@dataclass(frozen=True, kw_only=True)
class ListeningPeriod:
    """A slice of the listening history, from its first to its last play, with the tracks most played in it."""

    start: datetime
    end: datetime
    plays: int  # every play of the period, not only those of its tracks
    tracks: list[PeriodTrack]
