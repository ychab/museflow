from museflow.domain.entities.music import SuggestedTrack
from museflow.domain.entities.user import User
from museflow.domain.ports.advisors.client import AdvisorClientPort
from museflow.domain.ports.providers.library import ProviderLibraryPort
from museflow.domain.ports.repositories.music import TrackRepository


async def discover_tracks(
    user: User,
    track_repository: TrackRepository,
    provider_library: ProviderLibraryPort,
    advisor_client: AdvisorClientPort,
    seeds_top: bool = False,
    seeds_saved: bool = False,
    seeds_random: bool = False,
    seeds_limit: int = 50,
) -> list[SuggestedTrack]:
    # @TODO - order randomly? include top only? include saved only?
    track_seeds = await track_repository.get_list(user.id, limit=seeds_limit)

    tracks_suggested: list[SuggestedTrack] = []
    for track_seed in track_seeds:
        tracks_suggested += await advisor_client.get_similar_tracks(
            artist_name=", ".join([a.name for a in track_seed.artists]),
            track_name=track_seed.name,
        )

    # @todo 1 - use reconciler to transform them into spotify track
    # @todo 2 - filter them to remove know tracks by end-user
    # @todo 3 - order them by score
    tracks_suggested = sorted(tracks_suggested, key=lambda t: t.score or 0, reverse=True)

    # @todo 4 - and finally, SAVE them into a dedicated playlist

    return tracks_suggested  # @todo - return the new playlist created instead
