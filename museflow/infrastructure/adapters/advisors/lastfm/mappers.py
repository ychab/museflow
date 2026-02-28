from museflow.domain.entities.music import SuggestedTrack
from museflow.infrastructure.adapters.advisors.lastfm.schemas import LastFmTrack


def to_suggested_track(track: LastFmTrack) -> SuggestedTrack:
    return SuggestedTrack(
        name=track.name,
        artists=[track.artist.name],
        advisor_id=track.mbid,
        score=track.match,  # @todo - stick with a standard, and convert the lastFm match into score format (eg: 0.0 <> 1.0?)
    )
