from pydantic import HttpUrl

from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.clients.spotify import SpotifyClientPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.domain.ports.security import StateTokenGeneratorPort


async def oauth_redirect(
    user: User,
    auth_state_repository: OAuthProviderStateRepositoryPort,
    provider: MusicProvider,
    provider_client: SpotifyClientPort,
    state_token_generator: StateTokenGeneratorPort,
) -> HttpUrl:
    authorization_url, state = provider_client.get_authorization_url(
        state=state_token_generator.generate(),
    )

    await auth_state_repository.upsert(user_id=user.id, provider=provider, state=state)

    return authorization_url
