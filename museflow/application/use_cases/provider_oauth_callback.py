from museflow.domain.entities.user import User
from museflow.domain.exceptions import ProviderExchangeCodeError
from museflow.domain.mappers.auth import auth_token_create_from_token_payload
from museflow.domain.mappers.auth import auth_token_update_from_token_payload
from museflow.domain.ports.providers.client import ProviderOAuthClientPort
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.types import MusicProvider


async def oauth_callback(
    code: str,
    user: User,
    provider: MusicProvider,
    auth_token_repository: OAuthProviderTokenRepository,
    provider_client: ProviderOAuthClientPort,
) -> None:
    try:
        token_payload = await provider_client.exchange_code_for_token(code)
    except Exception as e:
        raise ProviderExchangeCodeError() from e

    auth_token = await auth_token_repository.get(user_id=user.id, provider=provider)

    if auth_token is not None:
        await auth_token_repository.update(
            user_id=user.id,
            provider=provider,
            auth_token_data=auth_token_update_from_token_payload(token_payload),
        )
    else:
        await auth_token_repository.create(
            user_id=user.id,
            provider=provider,
            auth_token_data=auth_token_create_from_token_payload(token_payload),
        )
