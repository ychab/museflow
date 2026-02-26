from museflow.domain.entities.user import User
from museflow.domain.exceptions import ProviderExchangeCodeError
from museflow.domain.ports.providers.client import ProviderOAuthClientPort
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.schemas.auth import OAuthProviderUserTokenCreate
from museflow.domain.schemas.auth import OAuthProviderUserTokenUpdate
from museflow.domain.types import MusicProvider


async def oauth_callback(
    code: str,
    user: User,
    provider: MusicProvider,
    auth_token_repository: OAuthProviderTokenRepository,
    provider_client: ProviderOAuthClientPort,
) -> None:
    try:
        token_state = await provider_client.exchange_code_for_token(code)
    except Exception as e:
        raise ProviderExchangeCodeError() from e

    auth_token = await auth_token_repository.get(user_id=user.id, provider=provider)

    if auth_token is not None:
        await auth_token_repository.update(
            user_id=user.id,
            provider=provider,
            auth_token_data=OAuthProviderUserTokenUpdate.from_token_state(token_state=token_state),
        )
    else:
        await auth_token_repository.create(
            user_id=user.id,
            provider=provider,
            auth_token_data=OAuthProviderUserTokenCreate.from_token_state(token_state=token_state),
        )
