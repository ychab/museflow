from pydantic import HttpUrl

from spotifagent.domain.entities.spotify import SpotifyScope
from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserUpdate
from spotifagent.domain.ports.clients.spotify import SpotifyClientPort
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import StateTokenGeneratorPort


async def spotify_oauth_redirect(
    user: User,
    user_repository: UserRepositoryPort,
    spotify_client: SpotifyClientPort,
    state_token_generator: StateTokenGeneratorPort,
) -> HttpUrl:
    authorization_url, state = spotify_client.get_authorization_url(
        scopes=SpotifyScope.required_scopes(),
        state=state_token_generator.generate(),
    )

    # Store the state to be retrieved by the callback endpoint.
    user_data = UserUpdate(spotify_state=state)
    await user_repository.update(user.id, user_data)

    return authorization_url
