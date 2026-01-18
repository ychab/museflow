import uuid
from typing import Any
from typing import cast

from polyfactory import Use
from polyfactory.decorators import post_generated
from slugify import slugify

from spotifagent.domain.entities.music import MusicProvider
from spotifagent.infrastructure.adapters.database.models import TopArtist
from spotifagent.infrastructure.adapters.database.models import TopTrack

from tests.integration.factories.base import BaseModelFactory
from tests.integration.factories.users import UserModelFactory


class BaseTopItemModelFactory[T: (TopArtist, TopTrack)](BaseModelFactory[T]):
    __is_base_factory__ = True

    name = Use(BaseModelFactory.__faker__.name)

    popularity = Use(BaseModelFactory.__faker__.random_int, min=0, max=100)
    provider = MusicProvider.SPOTIFY

    @post_generated
    @classmethod
    def slug(cls, name: str) -> str:
        return slugify(name)

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


class TopArtistModelFactory(BaseTopItemModelFactory[TopArtist]):
    __model__ = TopArtist

    genres = Use(lambda: ["Pop", "Rock", "Rap", "Indie", "Alternative"])


class TopTrackModelFactory(BaseTopItemModelFactory[TopTrack]):
    __model__ = TopTrack

    artists = Use(
        lambda: [
            {
                "name": BaseModelFactory.__faker__.name(),
                "provider_id": str(uuid.uuid4()),
            }
            for _ in range(BaseModelFactory.__faker__.random_int(min=1, max=3))
        ]
    )
