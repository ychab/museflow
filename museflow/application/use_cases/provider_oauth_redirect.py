from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.security import StateTokenGeneratorPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider


async def oauth_redirect(
    user: User,
    uow: UnitOfWorkPort,
    provider: MusicProvider,
    provider_oauth: ProviderOAuthPort,
    state_token_generator: StateTokenGeneratorPort,
) -> str:
    """Generates a URL to redirect the user for OAuth provider authentication.

    This function generates a state token, constructs the authorization URL,
    and stores the state in the repository to be verified at the callback stage.

    Args:
        user: The user entity initiating the authentication.
        uow: The unit of work giving access to the OAuth state repository.
        provider: The music provider to authenticate with.
        provider_oauth: The OAuth adapter for the provider.
        state_token_generator: The generator for creating a state token.

    Returns:
        The URL to redirect the user to for authentication.
    """
    state = state_token_generator.generate()
    authorization_url = provider_oauth.get_authorization_url(state=state)

    async with uow:
        await uow.auth_states.upsert(user_id=user.id, provider=provider, state=state)

    return authorization_url
