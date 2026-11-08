import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import cast

from sqlalchemy import select
from sqlalchemy import true
from sqlalchemy.ext.asyncio import AsyncSession

from polyfactory import Use

from museflow.domain.entities.track import Track as TrackEntity
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.models import Track
from museflow.infrastructure.adapters.database.models import TrackPlay
from museflow.infrastructure.adapters.database.repositories.track_play import TrackPlaySQLRepository

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TrackPlayModelFactory(BaseModelFactory[TrackPlay]):
    __model__ = TrackPlay


class TrackModelFactory(BaseModelFactory[Track]):
    __model__ = Track

    name = Use(BaseModelFactory.__faker__.name)
    # Never empty: the Track entity recomputes an empty fingerprint in __post_init__, breaking lookups by fingerprint.
    fingerprint = Use(BaseModelFactory.__faker__.sha256)

    score_skipped = False
    genres = Use(lambda: cast(list[str], []))
    moods = Use(lambda: cast(list[str], []))
    locales = None

    provider_links = Use(
        lambda: [{"provider": MusicProvider.SPOTIFY.value, "provider_id": str(BaseModelFactory.__faker__.uuid4())}]
    )

    artists = Use(lambda: [BaseModelFactory.__faker__.name()])
    album_name = Use(
        lambda: BaseModelFactory.__faker__.sentence(nb_words=3) if BaseModelFactory.__faker__.boolean() else None
    )

    @classmethod
    async def create_async(
        cls,
        *,
        played_count: int | None = None,
        played_at_first: datetime | None = None,
        played_at_last: datetime | None = None,
        **kwargs: Any,
    ) -> Track:
        """Creates the track, then the plays that give it the play data asked for: the track has no such columns.

        One play falls on each date given, the others a second apart after the first date (before the last one when
        only the last is given). No play data asked for means no play.
        """
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        track = await super().create_async(**kwargs)

        played_at = sorted({moment for moment in (played_at_first, played_at_last) if moment is not None})
        anchor, step = (played_at_last, -1) if played_at_first is None and played_at_last else (played_at_first, 1)
        anchor = anchor or datetime(2024, 1, 1, tzinfo=UTC)
        offset = 1
        while played_count is not None and len(played_at) < played_count:
            played_at.append(anchor + timedelta(seconds=step * offset))
            offset += 1

        for moment in played_at:
            await TrackPlayModelFactory.create_async(track_id=track.id, played_at=moment)
        return track

    @classmethod
    async def create_entity_async(cls, **kwargs: Any) -> TrackEntity:
        """Creates the track and its plays, as `create_async`, and returns it as the repositories load it."""
        track = await cls.create_async(**kwargs)
        session = cast(AsyncSession, cls.__async_session__)
        plays = TrackPlaySQLRepository.plays_summary()
        played_count, first, last = (
            await session.execute(
                select(plays.c.played_count, plays.c.played_at_first, plays.c.played_at_last)
                .select_from(Track)
                .join(plays, true())
                .where(Track.id == track.id)
            )
        ).one()
        return track.to_entity(played_count=played_count, played_at_first=first, played_at_last=last)

    @classmethod
    async def create_batch_async(cls, size: int, **kwargs: Any) -> list[Track]:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return [await cls.create_async(**kwargs) for _ in range(size)]

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
