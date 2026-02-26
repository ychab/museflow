from datetime import UTC
from datetime import datetime
from datetime import timedelta

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken


class OAuthProviderStateFactory(DataclassFactory[OAuthProviderState]):
    __model__ = OAuthProviderState


class OAuthProviderUserTokenFactory(DataclassFactory[OAuthProviderUserToken]):
    __model__ = OAuthProviderUserToken

    token_expires_at = Use(lambda: datetime.now(UTC) + timedelta(seconds=3600))
