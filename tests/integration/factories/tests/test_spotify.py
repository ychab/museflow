from pydantic import EmailStr
from pydantic import TypeAdapter

from spotifagent.domain.entities.users import User

from tests.integration.factories.spotify import SpotifyAccountModelFactory

email_adapter = TypeAdapter(EmailStr)


class TestSpotifyAccountModelFactory:
    async def test__create_user__provided(self, user: User) -> None:
        spotify_account_db = await SpotifyAccountModelFactory.create_async(user_id=user.id)
        assert spotify_account_db.user_id == user.id

    async def test__create_user__default(self) -> None:
        spotify_account_db = await SpotifyAccountModelFactory.create_async()
        assert spotify_account_db.user_id is not None
