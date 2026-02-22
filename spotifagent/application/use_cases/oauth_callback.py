from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import ProviderExchangeCodeError
from spotifagent.domain.ports.providers.client import ProviderOAuthClientPort
from spotifagent.domain.ports.repositories.spotify import SpotifyAccountRepositoryPort


async def oauth_callback(
    code: str,
    user: User,
    spotify_account_repository: SpotifyAccountRepositoryPort,
    provider_client: ProviderOAuthClientPort,
) -> None:
    try:
        token_state = await provider_client.exchange_code_for_token(code)
    except Exception as e:
        raise ProviderExchangeCodeError() from e

    # Update the spotify account if it's already exists, create it otherwise.
    if user.spotify_account:
        update_data = token_state.to_user_update()
        await spotify_account_repository.update(user.id, update_data)
    else:
        create_data = token_state.to_user_create()
        await spotify_account_repository.create(user.id, create_data)
