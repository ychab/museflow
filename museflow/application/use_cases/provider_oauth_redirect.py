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
    """Generates a URL to redirect the user for OAuth provider authentication.

    This function generates a state token, constructs the authorization URL,
    and stores the state in the repository to be verified at the callback stage.

    Args:
        user: The user entity initiating the authentication.
        auth_state_repository: The repository for storing OAuth state.
        provider: The music provider to authenticate with.
        provider_client: The client for the OAuth provider.
        state_token_generator: The generator for creating a state token.

    Returns:
        The URL to redirect the user to for authentication.
    """
    state = state_token_generator.generate()
    authorization_url = provider_client.get_authorization_url(state=state)

    await auth_state_repository.upsert(user_id=user.id, provider=provider, state=state)

    return authorization_url
