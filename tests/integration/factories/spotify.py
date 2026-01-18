from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from polyfactory import Use

from spotifagent.infrastructure.adapters.database.models import SpotifyAccount

from tests.integration.factories.base import BaseModelFactory


class SpotifyAccountModelFactory(BaseModelFactory[SpotifyAccount]):
    __model__ = SpotifyAccount

    token_type = "bearer"
    token_expires_at = Use(lambda: datetime.now(UTC) + timedelta(days=5))

    @classmethod
    async def create_async(cls, **kwargs: Any) -> SpotifyAccount:
        if "user_id" not in kwargs:
            from tests.integration.factories.users import UserModelFactory

            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)
