from typing import Any

from spotifagent.infrastructure.adapters.database.models import AuthProviderState

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
