from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserUpdate
from spotifagent.domain.exceptions import SpotifyExchangeCodeError
from spotifagent.domain.ports.clients.spotify import SpotifyClientPort
from spotifagent.domain.ports.repositories.spotify import SpotifyAccountRepositoryPort
from spotifagent.domain.ports.repositories.users import UserRepositoryPort


async def spotify_oauth_callback(
    code: str,
    user: User,
    user_repository: UserRepositoryPort,
    spotify_account_repository: SpotifyAccountRepositoryPort,
    spotify_client: SpotifyClientPort,
) -> None:
    try:
        token_state = await spotify_client.exchange_code_for_token(code)
    except Exception as e:
        raise SpotifyExchangeCodeError() from e

    # Update the spotify account if it's already exists, create it otherwise.
    if user.spotify_account:
        update_data = token_state.to_user_update()
        await spotify_account_repository.update(user.id, update_data)
    else:
        create_data = token_state.to_user_create()
        await spotify_account_repository.create(user.id, create_data)

    # Finally, clean up the spotify auth state.
    await user_repository.update(user.id, UserUpdate(spotify_state=None))
