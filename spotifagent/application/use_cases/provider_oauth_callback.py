from spotifagent.domain.entities.auth import OAuthProviderUserTokenCreate
from spotifagent.domain.entities.auth import OAuthProviderUserTokenUpdate
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import ProviderExchangeCodeError
from spotifagent.domain.ports.providers.client import ProviderOAuthClientPort
from spotifagent.domain.ports.repositories.auth import OAuthProviderTokenRepositoryPort


async def oauth_callback(
    code: str,
    user: User,
    provider: MusicProvider,
    auth_token_repository: OAuthProviderTokenRepositoryPort,
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
