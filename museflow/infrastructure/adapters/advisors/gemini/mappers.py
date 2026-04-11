from museflow.domain.entities.music import TrackSuggested
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiDiscoveryStrategyContent
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiSuggestedTrack


def to_track_suggested(track: GeminiSuggestedTrack) -> TrackSuggested:
    return TrackSuggested(
        name=track.name,
        artists=track.artists,
        advisor_id=None,
        score=max(0.0, min(1.0, track.score)),
    )


def to_discovery_strategy(content: GeminiDiscoveryStrategyContent) -> DiscoveryTasteStrategy:
    return DiscoveryTasteStrategy(
        reasoning=content.reasoning,
        strategy_label=content.strategy_label,
        recommended_tracks=[to_track_suggested(t) for t in content.recommended_tracks],
        search_queries=content.search_queries,
        suggested_playlist_name=content.suggested_playlist_name,
    )
