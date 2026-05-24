import uuid
from typing import Any
from typing import cast

from sqlalchemy import select

from polyfactory import Use
from polyfactory.factories import TypedDictFactory

from museflow.domain.types import AlbumType
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models import AlbumDict
from museflow.infrastructure.adapters.database.models import ArtistDict
from museflow.infrastructure.adapters.database.models import Track

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class ArtistDictFactory(TypedDictFactory[ArtistDict]):
    __model__ = ArtistDict


class AlbumDictFactory(TypedDictFactory[AlbumDict]):
    __model__ = AlbumDict

    album_type = Use(
        lambda: (
            TypedDictFactory.__faker__.random_element(AlbumType)
            if TypedDictFactory.__faker__.boolean(chance_of_getting_true=80)
            else None
        )
    )


class TrackModelFactory(BaseModelFactory[Track]):
    __model__ = Track

    name = Use(BaseModelFactory.__faker__.name)
    provider = MusicProvider.SPOTIFY
    provider_id = Use(BaseModelFactory.__faker__.uuid4)

    artists = Use(
        lambda: [ArtistDictFactory.build() for _ in range(BaseModelFactory.__faker__.random_int(min=1, max=3))]
    )

    album = Use(
        lambda: AlbumDictFactory.build() if BaseModelFactory.__faker__.boolean(chance_of_getting_true=70) else None
    )

    @classmethod
    async def create_async(cls, **kwargs: Any) -> Track:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return cast(Track, await super().create_async(**kwargs))

    @classmethod
    async def create_batch_async(cls, size: int, **kwargs: Any) -> list[Track]:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return cast(list[Track], await super().create_batch_async(size=size, **kwargs))

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
