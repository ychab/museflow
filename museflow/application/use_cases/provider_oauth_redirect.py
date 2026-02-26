from pydantic import HttpUrl

from museflow.domain.entities.user import User
from museflow.domain.ports.providers.client import ProviderOAuthClientPort
from museflow.domain.ports.repositories.auth import OAuthProviderStateRepository
from museflow.domain.ports.security import StateTokenGeneratorPort
from museflow.domain.types import MusicProvider


async def oauth_redirect(
    user: User,
    auth_state_repository: OAuthProviderStateRepository,
    provider: MusicProvider,
    provider_client: ProviderOAuthClientPort,
    state_token_generator: StateTokenGeneratorPort,
) -> HttpUrl:
    state = state_token_generator.generate()
    authorization_url = provider_client.get_authorization_url(state=state)

    await auth_state_repository.upsert(user_id=user.id, provider=provider, state=state)

    return authorization_url
