import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

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
        track_ids: list[uuid.UUID] = kwargs.pop("track_ids", [])

        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        if "profile_id" not in kwargs:
            taste_profile = await TasteProfileModelFactory.create_async(user_id=kwargs["user_id"])
            kwargs["profile_id"] = taste_profile.id

        playlist = await super().create_async(**kwargs)

        if track_ids:
            session = cls.__async_session__
            assert isinstance(session, AsyncSession)
            for i, track_id in enumerate(track_ids):
                session.add(DiscoveryPlaylistTrackModel(playlist_id=playlist.id, track_id=track_id, position=i))
            await session.flush()

        return playlist
