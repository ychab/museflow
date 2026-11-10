from museflow.domain.entities.track import Track
from museflow.domain.utils.text import strip_control_chars
from museflow.domain.value_objects.taste import ArtistSuggested
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.domain.value_objects.taste import TrackPicked
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryArtistsResponse
from museflow.infrastructure.adapters.advisors.openrouter.schemas import DiscoveryPicksResponse


def to_discovery_artist_strategy(content: DiscoveryArtistsResponse) -> DiscoveryArtistStrategy:
    return DiscoveryArtistStrategy(
        reasoning=content.reasoning,
        strategy_label=content.strategy_label,
        # Nothing to search when a name holds nothing but control characters.
        artists=[
            ArtistSuggested(name=name, sound=artist.sound, score=_clamp_score(artist.score))
            for artist in content.recommended_artists
            if (name := strip_control_chars(artist.name))
        ],
        suggested_playlist_name=content.suggested_playlist_name,
    )


def to_tracks_picked(content: DiscoveryPicksResponse, candidates: dict[str, Track]) -> list[TrackPicked]:
    """Maps the picked ids back to the candidates: an id the advisor made up, or picked twice, is dropped."""
    tracks_picked: list[TrackPicked] = []
    seen: set[str] = set()
    for pick in content.picks:
        pick_id = pick.id.strip()
        track = candidates.get(pick_id)
        if track is None or pick_id in seen:
            continue
        seen.add(pick_id)
        tracks_picked.append(TrackPicked(track=track, score=_clamp_score(pick.score)))
    return tracks_picked


def _clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))
