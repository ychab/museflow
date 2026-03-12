from museflow.domain.entities.music import TrackSuggested
from museflow.infrastructure.adapters.advisors.lastfm.schemas import LastFmTrack


def to_track_suggested(track: LastFmTrack) -> TrackSuggested:
    return TrackSuggested(
        name=track.name,
        artists=[track.artist.name],
        advisor_id=track.mbid,
        score=track.match,
        duration_ms=track.duration * 1000 if track.duration else None,
    )
