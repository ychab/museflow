from museflow.application.mappers.auth import to_auth_token_create_input
from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderExchangeCodeError


async def exchange_oauth_code(
    code: str,
    user: User,
    provider: MusicProvider,
    uow: UnitOfWorkPort,
    provider_oauth: ProviderOAuthPort,
) -> None:
    """Exchanges the authorization code for a token and saves it, created or updated, for the user.

    The second step of the OAuth flow: the provider sends the code to the callback once the user has granted access.

    Args:
        code: The authorization code received from the OAuth provider.
        user: The user who started the flow.
        provider: The music provider (e.g., Spotify).
        uow: The unit of work giving access to the OAuth token repository.
        provider_oauth: The OAuth adapter for the provider.

    Raises:
        ProviderExchangeCodeError: If there's an error during the code exchange.
    """
    try:
        token_payload = await provider_oauth.exchange_code_for_token(code)
    except Exception as e:
        raise ProviderExchangeCodeError() from e

    async with uow:
        await uow.auth_tokens.upsert(
            user_id=user.id,
            provider=provider,
            auth_token_in=to_auth_token_create_input(token_payload),
        )
