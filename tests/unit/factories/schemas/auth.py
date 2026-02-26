from datetime import UTC
from datetime import datetime
from datetime import timedelta

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from museflow.domain.schemas.auth import OAuthProviderTokenState
from museflow.domain.schemas.auth import OAuthProviderUserTokenCreate
from museflow.domain.schemas.auth import OAuthProviderUserTokenUpdate


class OAuthProviderTokenStateFactory(ModelFactory[OAuthProviderTokenState]):
    __model__ = OAuthProviderTokenState

    expires_at = Use(lambda: datetime.now(UTC) + timedelta(seconds=3600))


class OAuthProviderUserTokenCreateFactory(ModelFactory[OAuthProviderUserTokenCreate]):
    __model__ = OAuthProviderUserTokenCreate


class OAuthProviderUserTokenUpdateFactory(ModelFactory[OAuthProviderUserTokenUpdate]):
    __model__ = OAuthProviderUserTokenUpdate
    __allow_none_optionals__ = False
