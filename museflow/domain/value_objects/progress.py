from dataclasses import dataclass

from museflow.domain.entities.playlist import Playlist
from museflow.domain.enums import ProgressStep
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.domain.value_objects.taste import TrackPicked

# The events a long-running flow publishes to its progress display: data only, each display words them its own way.


@dataclass(frozen=True, kw_only=True)
class StepStarted:
    step: ProgressStep
    attempt: int | None = None  # in a flow that runs its steps over several attempts
    max_attempts: int | None = None


@dataclass(frozen=True, kw_only=True)
class StrategyChosen:
    attempt: int
    strategy: DiscoveryArtistStrategy


@dataclass(frozen=True, kw_only=True)
class CandidatesFound:
    attempt: int
    artists: int  # searched
    artists_kept: int  # with at least one track the user does not know
    tracks: int  # the user does not know, offered to the advisor


@dataclass(frozen=True, kw_only=True)
class PicksMade:
    attempt: int
    picks: list[TrackPicked]
    kept: int  # tracks the playlist holds now, after the per-artist cap
    target: int


@dataclass(frozen=True, kw_only=True)
class PlaylistCreated:
    playlist: Playlist


# Here rather than in domain/types.py, which the entities these events carry import: a cycle.
type ProgressEvent = StepStarted | StrategyChosen | CandidatesFound | PicksMade | PlaylistCreated
