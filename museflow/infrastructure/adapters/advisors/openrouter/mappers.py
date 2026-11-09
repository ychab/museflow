from museflow.domain.entities.track import TrackSuggested
from museflow.domain.utils.text import strip_control_chars
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryStrategyResponse
from museflow.infrastructure.adapters.advisors.openrouter.schemas import SuggestedTrack


def to_track_suggested(track: SuggestedTrack) -> TrackSuggested | None:
    """Returns None when a name holds nothing but control characters, as nothing is left to search."""
    name = strip_control_chars(track.name)
    artists = [artist for artist in map(strip_control_chars, track.artists) if artist]
    if not name or not artists:
        return None

    return TrackSuggested(
        name=name,
        artists=artists,
        advisor_id=None,
        score=max(0.0, min(1.0, track.score)),
    )


def to_discovery_strategy(content: DiscoveryStrategyResponse) -> DiscoveryTasteStrategy:
    return DiscoveryTasteStrategy(
        reasoning=content.reasoning,
        strategy_label=content.strategy_label,
        recommended_tracks=[
            track_suggested
            for track in content.recommended_tracks
            if (track_suggested := to_track_suggested(track)) is not None
        ],
        suggested_playlist_name=content.suggested_playlist_name,
    )
