from datetime import UTC
from datetime import datetime
from datetime import timedelta

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from museflow.domain.schemas.auth import OAuthProviderTokenPayload


class OAuthProviderTokenPayloadFactory(ModelFactory[OAuthProviderTokenPayload]):
    __model__ = OAuthProviderTokenPayload

    expires_at = Use(lambda: datetime.now(UTC) + timedelta(seconds=3600))
