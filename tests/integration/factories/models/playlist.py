import uuid
from typing import Any

from polyfactory.decorators import post_generated

from museflow.domain.types import PlaylistType
from museflow.infrastructure.adapters.database.models.playlist import Playlist as PlaylistModel
from museflow.infrastructure.adapters.database.models.playlist import PlaylistTrack as PlaylistTrackModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.taste import TasteProfileModelFactory
from tests.integration.factories.models.track import TrackModelFactory
from tests.integration.factories.models.user import UserModelFactory


class PlaylistModelFactory(BaseModelFactory[PlaylistModel]):
    __model__ = PlaylistModel

    @post_generated
    @classmethod
    def profile_id(cls) -> uuid.UUID | None:
        # create_async injects the real FK value explicitly via kwargs when type == DISCOVERY.
        return None

    @post_generated
    @classmethod
    def reasoning(cls, type: PlaylistType) -> str | None:
        return cls.__faker__.paragraph() if type == PlaylistType.DISCOVERY else None

    @post_generated
    @classmethod
    def genre(cls, type: PlaylistType) -> str | None:
        return cls.__faker__.word() if type == PlaylistType.DISCOVERY else None

    @post_generated
    @classmethod
    def mood(cls, type: PlaylistType) -> str | None:
        return cls.__faker__.word() if type == PlaylistType.DISCOVERY else None

    @post_generated
    @classmethod
    def custom_instructions(cls, type: PlaylistType) -> str | None:
        return cls.__faker__.sentence() if type == PlaylistType.DISCOVERY else None

    @classmethod
    async def create_async(cls, **kwargs: Any) -> PlaylistModel:
        track_ids: list[uuid.UUID] | None = kwargs.pop("track_ids", None)
        playlist_type: PlaylistType = kwargs.get("type", PlaylistType.DISCOVERY)

        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        if playlist_type == PlaylistType.DISCOVERY and "profile_id" not in kwargs:
            taste_profile = await TasteProfileModelFactory.create_async(user_id=kwargs["user_id"])
            kwargs["profile_id"] = taste_profile.id

        if track_ids is None:
            tracks = await TrackModelFactory.create_batch_async(3, user_id=kwargs["user_id"])
            track_ids = [track.id for track in tracks]

        playlist = await super().create_async(**kwargs)

        if track_ids:
            session = cls.__async_session__
            for i, track_id in enumerate(track_ids):
                session.add(PlaylistTrackModel(playlist_id=playlist.id, track_id=track_id, position=i))  # type: ignore[union-attr]
            await session.flush()  # type: ignore[union-attr]

        return playlist
