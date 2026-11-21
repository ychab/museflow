from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from polyfactory import Use

from museflow.infrastructure.adapters.database.models import AuthProviderStateModel
from museflow.infrastructure.adapters.database.models import AuthProviderTokenModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class AuthProviderStateModelFactory(BaseModelFactory[AuthProviderStateModel]):
    __model__ = AuthProviderStateModel

    # Never empty: String(n) gives polyfactory no min length, and the OAuth callback rejects an empty state.
    state = Use(BaseModelFactory.__faker__.sha256)

    @classmethod
    async def create_async(cls, **kwargs: Any) -> AuthProviderStateModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)


class AuthProviderTokenFactory(BaseModelFactory[AuthProviderTokenModel]):
    __model__ = AuthProviderTokenModel

    # The tokens are random bytes, not a ciphertext: a row that must decrypt is saved through the repository (the
    # `auth_token` fixture).
    token_type = "bearer"
    token_expires_at = Use(lambda: datetime.now(UTC) + timedelta(days=5))

    @classmethod
    async def create_async(cls, **kwargs: Any) -> AuthProviderTokenModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)
