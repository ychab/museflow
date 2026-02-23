from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from polyfactory import Use

from spotifagent.infrastructure.adapters.database.models import AuthProviderState
from spotifagent.infrastructure.adapters.database.models import AuthProviderToken

from tests.integration.factories.base import BaseModelFactory
from tests.integration.factories.users import UserModelFactory


class AuthProviderStateModelFactory(BaseModelFactory[AuthProviderState]):
    __model__ = AuthProviderState

    @classmethod
    async def create_async(cls, **kwargs: Any) -> AuthProviderState:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)


class AuthProviderTokenFactory(BaseModelFactory[AuthProviderToken]):
    __model__ = AuthProviderToken

    token_type = "bearer"
    token_expires_at = Use(lambda: datetime.now(UTC) + timedelta(days=5))

    @classmethod
    async def create_async(cls, **kwargs: Any) -> AuthProviderToken:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)
