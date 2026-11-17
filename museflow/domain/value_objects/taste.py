from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import TypedDict

from museflow.domain.entities.track import Track


class TechnicalFingerprint(TypedDict):
    energy: float
    acousticness: float
    rhythmic_complexity: float
    atmospheric: float
    instrumentalness: float


class TasteEra(TypedDict):
    era_label: str  # AI-generated name, e.g. "The Post-Rock Exploration"
    time_range: str  # e.g. "2021-2023"
    technical_fingerprint: TechnicalFingerprint
    dominant_moods: list[str]


class TasteProfileData(TypedDict):
    taste_timeline: list[TasteEra]  # chronological map of taste eras
    core_identity: dict[str, float]  # stable DNA, e.g. {"progressive metal": 0.8}
    current_vibe: dict[str, float]  # active trajectory (last ~400 tracks)

    # Populated by final psychographic reflection only
    personality_archetype: str | None
    life_phase_insights: list[str]

    # Populated by final psychographic reflection only
    musical_identity_summary: str | None  # 2-3 sentence narrative of the listener's evolution
    behavioral_traits: dict[str, float]  # e.g. {"openness": 0.9, "rhythmic_dependency": 0.7}
    discovery_style: str | None  # e.g. "The Digger" or "The Loyalist"


@dataclass(frozen=True, kw_only=True)
class ArtistSuggested:
    name: str
    sound: str  # what the advisor wants from this artist for the request, to guide the pick among their tracks
    score: float
    # The request asks for this artist's own tracks ("tracks of X I don't know"), not for their sound: their search
    # goes deeper and their tracks are not capped per artist.
    requested: bool = False


@dataclass(frozen=True, kw_only=True)
class DiscoveryArtistStrategy:
    reasoning: str
    strategy_label: str
    artists: list[ArtistSuggested]
    suggested_playlist_name: str


@dataclass(frozen=True, kw_only=True)
class ArtistSearch:
    """What the catalogue search of one artist gave: its tracks the user does not know are offered to the advisor."""

    artist: str
    found: int = 0  # catalogue tracks the search returned
    matched: int = 0  # among them, those crediting the artist
    tracks: list[Track] = field(default_factory=list)  # among those, the tracks the user does not know
    rejected: bool = False  # the provider refused the search query


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
