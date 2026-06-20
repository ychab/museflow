from typing import Any

from polyfactory import Use

from museflow.infrastructure.adapters.database.models.blacklist import BlacklistedArtist as BlacklistedArtistModel
from museflow.infrastructure.adapters.database.models.blacklist import BlacklistedTrack as BlacklistedTrackModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class BlacklistedArtistModelFactory(BaseModelFactory[BlacklistedArtistModel]):
    __model__ = BlacklistedArtistModel

    artist_name = Use(BaseModelFactory.__faker__.name)

    @classmethod
    async def create_async(cls, **kwargs: Any) -> BlacklistedArtistModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id
        return await super().create_async(**kwargs)


class BlacklistedTrackModelFactory(BaseModelFactory[BlacklistedTrackModel]):
    __model__ = BlacklistedTrackModel

    name = Use(BaseModelFactory.__faker__.name)
    artist_name = Use(BaseModelFactory.__faker__.name)

    @classmethod
    async def create_async(cls, **kwargs: Any) -> BlacklistedTrackModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id
        return await super().create_async(**kwargs)
