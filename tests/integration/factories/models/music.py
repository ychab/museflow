import uuid
from typing import Any
from typing import cast

from sqlalchemy import select

from polyfactory import Use
from polyfactory.factories import TypedDictFactory

from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models import AlbumDict
from museflow.infrastructure.adapters.database.models import Artist
from museflow.infrastructure.adapters.database.models import ArtistDict
from museflow.infrastructure.adapters.database.models import Track

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class BaseMusicItemModelFactory[T: (Artist | Track)](BaseModelFactory[T]):
    __is_base_factory__ = True

    name = Use(BaseModelFactory.__faker__.name)

    popularity = Use(BaseModelFactory.__faker__.random_int, min=0, max=100)
    top_position = Use(BaseModelFactory.__faker__.random_int, min=1)

    genres = Use(lambda: ["Pop", "Rock", "Rap", "Indie", "Alternative"])

    provider = MusicProvider.SPOTIFY

    @classmethod
    async def create_async(cls, **kwargs: Any) -> T:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return cast(T, await super().create_async(**kwargs))

    @classmethod
    async def create_batch_async(cls, size: int, **kwargs: Any) -> list[T]:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return cast(list[T], await super().create_batch_async(size=size, **kwargs))


class ArtistModelFactory(BaseMusicItemModelFactory[Artist]):
    __model__ = Artist


class ArtistDictFactory(TypedDictFactory[ArtistDict]):
    __model__ = ArtistDict


class AlbumDictFactory(TypedDictFactory[AlbumDict]):
    __model__ = AlbumDict


class TrackModelFactory(BaseMusicItemModelFactory[Track]):
    __model__ = Track

    artists = Use(
        lambda: [
            ArtistDictFactory.build() for _ in range(BaseMusicItemModelFactory.__faker__.random_int(min=1, max=3))
        ]
    )

    album = Use(
        lambda: (
            AlbumDictFactory.build()
            if BaseMusicItemModelFactory.__faker__.boolean(chance_of_getting_true=70)
            else None
        )
    )

    @classmethod
    async def get_or_create(cls, user_id: uuid.UUID, provider_id: str, **kwargs: Any) -> tuple[Track, bool]:
        if not user_id or not provider_id:
            raise ValueError("You must provide 'user_id' and 'provider_id' for uniqueness.")

        session = cls.__async_session__
        stmt = select(cls.__model__).filter_by(user_id=user_id, provider_id=provider_id)
        result = await session.execute(stmt)  # type: ignore[union-attr]
        instance = result.scalar_one_or_none()

        if instance:
            return instance, False

        instance = await cls.create_async(user_id=user_id, provider_id=provider_id, **kwargs)
        return instance, True
