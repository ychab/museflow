from museflow.domain.entities.music import TrackSuggested
from museflow.infrastructure.adapters.advisors.gemini.schemas import GeminiSuggestedTrack


def to_track_suggested(track: GeminiSuggestedTrack) -> TrackSuggested:
    return TrackSuggested(
        name=track.name,
        artists=track.artists,
        advisor_id=None,
        score=max(0.0, min(1.0, track.score)),
    )
