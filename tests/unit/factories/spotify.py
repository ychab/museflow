from datetime import UTC
from datetime import datetime
from datetime import timedelta

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from spotifagent.domain.entities.spotify import SpotifyAccount
from spotifagent.domain.entities.spotify import SpotifyAccountCreate
from spotifagent.domain.entities.spotify import SpotifyAccountUpdate
from spotifagent.domain.entities.spotify import SpotifyTokenState

# --- Pydantic domain layer ---


class SpotifyAccountFactory(ModelFactory[SpotifyAccount]):
    __model__ = SpotifyAccount
    __set_as_default_factory_for_type__ = True


class SpotifyAccountCreateFactory(ModelFactory[SpotifyAccountCreate]):
    __model__ = SpotifyAccountCreate


class SpotifyAccountUpdateFactory(ModelFactory[SpotifyAccountUpdate]):
    __model__ = SpotifyAccountUpdate
    __allow_none_optionals__ = False


# --- Pydantic app layer ---


class SpotifyTokenStateFactory(ModelFactory[SpotifyTokenState]):
    __model__ = SpotifyTokenState

    expires_at = Use(lambda: datetime.now(UTC) + timedelta(seconds=3600))
