from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from polyfactory import Use
from polyfactory.decorators import post_generated

from spotifagent.infrastructure.adapters.database.models import User

from tests.integration.factories.base import BaseModelFactory


class UserModelFactory(BaseModelFactory[User]):
    __model__ = User

    email = Use(BaseModelFactory.__faker__.email)

    is_active = True

    spotify_state = None

    @post_generated
    @classmethod
    def hashed_password(cls, password: str = "testtest") -> str:
        from tests.integration.conftest import get_password_hasher

        return get_password_hasher().hash(password)

    @classmethod
    async def create_async(cls, **kwargs: Any) -> User:
        with_spotify_account = kwargs.pop("with_spotify_account", False)

        user = await super().create_async(**kwargs)

        if with_spotify_account:
            from tests.integration.factories.spotify import SpotifyAccountModelFactory  # Prevent circular import

            await SpotifyAccountModelFactory.create_async(user_id=user.id)

        # Explicitly load the relationship to avoid Lazy Load DB errors due to async session.
        # We cannot just refresh with its attributes.
        session = cls.__async_session__
        stmt = select(User).options(selectinload(User.spotify_account)).where(User.id == user.id)
        result = await session.execute(stmt)  # type: ignore[union-attr]

        return result.scalar_one()
