import uuid
from typing import Any

from museflow.infrastructure.adapters.database.models.discovery import DiscoveryPlaylist as DiscoveryPlaylistModel
from museflow.infrastructure.adapters.database.models.discovery import (
    DiscoveryPlaylistTrack as DiscoveryPlaylistTrackModel,
)

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.user import UserModelFactory


class DiscoveryPlaylistModelFactory(BaseModelFactory[DiscoveryPlaylistModel]):
    __model__ = DiscoveryPlaylistModel

    genre = None
    mood = None
    custom_instructions = None

    @classmethod
    async def create_async(cls, **kwargs: Any) -> DiscoveryPlaylistModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        if "profile_id" not in kwargs:
            taste_profile = await TasteProfileModelFactory.create_async(user_id=kwargs["user_id"])
            kwargs["profile_id"] = taste_profile.id

        return await super().create_async(**kwargs)


class DiscoveryPlaylistTrackModelFactory(BaseModelFactory[DiscoveryPlaylistTrackModel]):
    __model__ = DiscoveryPlaylistTrackModel

    score = None
    artist_names = ["Test Artist"]

    @classmethod
    async def create_async(cls, **kwargs: Any) -> DiscoveryPlaylistTrackModel:
        if "playlist_id" not in kwargs:
            playlist = await DiscoveryPlaylistModelFactory.create_async(user_id=kwargs.get("user_id", uuid.uuid4()))
            kwargs["playlist_id"] = playlist.id
        return await super().create_async(**kwargs)
