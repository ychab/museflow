import uuid
from typing import Any
from typing import cast

from sqlalchemy import select

from polyfactory import Use

from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.database.models import Track

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TrackModelFactory(BaseModelFactory[Track]):
    __model__ = Track

    name = Use(BaseModelFactory.__faker__.name)
    score_skipped = False
    provider_links = Use(
        lambda: [{"provider": MusicProvider.SPOTIFY.value, "provider_id": str(BaseModelFactory.__faker__.uuid4())}]
    )

    artists = Use(lambda: [BaseModelFactory.__faker__.name()])
    album_name = Use(
        lambda: BaseModelFactory.__faker__.sentence(nb_words=3) if BaseModelFactory.__faker__.boolean() else None
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
    async def get_or_create(cls, user_id: uuid.UUID, fingerprint: str, **kwargs: Any) -> tuple[Track, bool]:
        if not user_id or not fingerprint:
            raise ValueError("You must provide 'user_id' and 'fingerprint' for uniqueness.")

        session = cls.__async_session__
        stmt = select(cls.__model__).filter_by(user_id=user_id, fingerprint=fingerprint)
        result = await session.execute(stmt)  # type: ignore[union-attr]
        instance = result.scalar_one_or_none()

        if instance:
            return instance, False

        instance = await cls.create_async(user_id=user_id, fingerprint=fingerprint, **kwargs)
        return instance, True
