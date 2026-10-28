from museflow.application.mappers.auth import auth_token_create_from_token_payload
from museflow.application.mappers.auth import auth_token_update_from_token_payload
from museflow.application.ports.providers.oauth import ProviderOAuthPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderExchangeCodeError


async def oauth_callback(
    code: str,
    user: User,
    provider: MusicProvider,
    uow: UnitOfWorkPort,
    provider_oauth: ProviderOAuthPort,
) -> None:
    """Handles the OAuth callback from a music provider.

    This function exchanges the authorization code for an access token, then
    creates or updates the user's authentication token in the repository.

    Args:
        code: The authorization code received from the OAuth provider.
        user: The user entity for whom the callback is being processed.
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
        auth_token = await uow.auth_tokens.get(user_id=user.id, provider=provider)

        if auth_token is not None:
            await uow.auth_tokens.update(
                user_id=user.id,
                provider=provider,
                auth_token_data=auth_token_update_from_token_payload(token_payload),
            )
        else:
            await uow.auth_tokens.create(
                user_id=user.id,
                provider=provider,
                auth_token_data=auth_token_create_from_token_payload(token_payload),
            )
