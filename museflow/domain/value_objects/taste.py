from dataclasses import dataclass

from museflow.domain.entities.track import TrackSuggested


@dataclass(frozen=True, kw_only=True)
class DiscoveryTasteStrategy:
    reasoning: str
    strategy_label: str
    recommended_tracks: list[TrackSuggested]
    suggested_playlist_name: str
