from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from polyfactory import Use

from museflow.infrastructure.adapters.database.models import AuthProviderState
from museflow.infrastructure.adapters.database.models import AuthProviderToken

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class AuthProviderStateModelFactory(BaseModelFactory[AuthProviderState]):
    __model__ = AuthProviderState

    # Never empty: String(n) gives polyfactory no min length, and the OAuth callback rejects an empty state.
    state = Use(BaseModelFactory.__faker__.sha256)

    @classmethod
    async def create_async(cls, **kwargs: Any) -> AuthProviderState:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)


class AuthProviderTokenFactory(BaseModelFactory[AuthProviderToken]):
    __model__ = AuthProviderToken

    token_type = "bearer"
    # Never empty: String(n) gives polyfactory no min length, and an empty token makes an illegal Authorization header.
    token_access = Use(BaseModelFactory.__faker__.sha256)
    token_refresh = Use(BaseModelFactory.__faker__.sha256)
    token_expires_at = Use(lambda: datetime.now(UTC) + timedelta(days=5))

    @classmethod
    async def create_async(cls, **kwargs: Any) -> AuthProviderToken:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)
