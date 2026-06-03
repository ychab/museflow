from museflow.application.inputs.discovery import BlacklistChoiceInput
from museflow.application.inputs.discovery import DiscoveryPlaylistRatingInput
from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.application.ports.repositories.discovery import DiscoveryPlaylistRepository
from museflow.domain.entities.user import User


async def discovery_playlist_rate(
    user: User,
    ratings: list[DiscoveryPlaylistRatingInput],
    blacklist_choices: list[BlacklistChoiceInput],
    discovery_playlist_repository: DiscoveryPlaylistRepository,
    blacklist_repository: BlacklistRepository,
) -> None:
    for rating in ratings:
        await discovery_playlist_repository.rate_track(user.id, rating.track_id, rating.score)
    for choice in blacklist_choices:
        if choice.blacklist_track:
            await blacklist_repository.add_track(user.id, choice.track_name, choice.artist_name)
        if choice.blacklist_artist:
            await blacklist_repository.add_artist(user.id, choice.artist_name)
