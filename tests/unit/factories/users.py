import base64

from polyfactory.decorators import post_generated
from polyfactory.factories.pydantic_factory import ModelFactory

from spotifagent.domain.entities.spotify import SpotifyAccount
from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserCreate
from spotifagent.domain.entities.users import UserUpdate

from tests.unit.factories.spotify import SpotifyAccountFactory


class UserFactory(ModelFactory[User]):
    __model__ = User

    is_active = True

    @post_generated
    @classmethod
    def hashed_password(cls, password: str = "testtest") -> str:
        return base64.b64encode(password.encode()).decode()

    @post_generated
    @classmethod
    def spotify_account(cls, with_spotify_account: bool = False) -> SpotifyAccount | None:
        return SpotifyAccountFactory.build() if with_spotify_account else None


class UserCreateFactory(ModelFactory[UserCreate]):
    __model__ = UserCreate


class UserUpdateFactory(ModelFactory[UserUpdate]):
    __model__ = UserUpdate
    __allow_none_optionals__ = False
