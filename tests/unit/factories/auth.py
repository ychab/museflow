from datetime import UTC
from datetime import datetime
from datetime import timedelta

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from spotifagent.domain.entities.auth import OAuthProviderState
from spotifagent.domain.entities.auth import OAuthProviderTokenState
from spotifagent.domain.entities.auth import OAuthProviderUserToken
from spotifagent.domain.entities.auth import OAuthProviderUserTokenCreate
from spotifagent.domain.entities.auth import OAuthProviderUserTokenUpdate


class OAuthProviderStateFactory(ModelFactory[OAuthProviderState]):
    __model__ = OAuthProviderState


class OAuthProviderTokenStateFactory(ModelFactory[OAuthProviderTokenState]):
    __model__ = OAuthProviderTokenState

    expires_at = Use(lambda: datetime.now(UTC) + timedelta(seconds=3600))


class OAuthProviderUserTokenFactory(ModelFactory[OAuthProviderUserToken]):
    __model__ = OAuthProviderUserToken

    token_expires_at = Use(lambda: datetime.now(UTC) + timedelta(seconds=3600))


class OAuthProviderUserTokenCreateFactory(ModelFactory[OAuthProviderUserTokenCreate]):
    __model__ = OAuthProviderUserTokenCreate


class OAuthProviderUserTokenUpdateFactory(ModelFactory[OAuthProviderUserTokenUpdate]):
    __model__ = OAuthProviderUserTokenUpdate
    __allow_none_optionals__ = False
