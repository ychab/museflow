from pydantic import HttpUrl

from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.domain.ports.providers.client import ProviderOAuthClientPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderStateRepositoryPort
from spotifagent.domain.ports.security import StateTokenGeneratorPort


async def oauth_redirect(
    user: User,
    auth_state_repository: OAuthProviderStateRepositoryPort,
    provider: MusicProvider,
    provider_client: ProviderOAuthClientPort,
    state_token_generator: StateTokenGeneratorPort,
) -> HttpUrl:
    state = state_token_generator.generate()
    authorization_url = provider_client.get_authorization_url(state=state)

    await auth_state_repository.upsert(user_id=user.id, provider=provider, state=state)

    return authorization_url
