from datetime import UTC
from datetime import datetime
from datetime import timedelta

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from spotifagent.domain.entities.auth import OAuthProviderState
from spotifagent.domain.entities.auth import OAuthProviderTokenState


class OAuthProviderStateFactory(ModelFactory[OAuthProviderState]):
    __model__ = OAuthProviderState


class OAuthProviderTokenStateFactory(ModelFactory[OAuthProviderTokenState]):
    __model__ = OAuthProviderTokenState

    expires_at = Use(lambda: datetime.now(UTC) + timedelta(seconds=3600))
