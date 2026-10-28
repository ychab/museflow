from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderStateSQLRepository
from museflow.infrastructure.adapters.database.repositories.auth import OAuthProviderTokenSQLRepository
from museflow.infrastructure.adapters.database.repositories.blacklist import BlacklistSQLRepository
from museflow.infrastructure.adapters.database.repositories.playlist import PlaylistSQLRepository
from museflow.infrastructure.adapters.database.repositories.taste import TasteProfileSQLRepository
from museflow.infrastructure.adapters.database.repositories.track import TrackSQLRepository
from museflow.infrastructure.adapters.database.repositories.users import UserSQLRepository


class SQLUnitOfWork(UnitOfWorkPort):
    """Opens a new session for each block and closes it on exit, which returns the connection to the pool."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        self.session: AsyncSession | None = None
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        if self.session is not None:
            raise RuntimeError("A unit of work block is already open")

        session = self.session_factory()
        self.session = session
        self.rolled_back = False

        self.users = UserSQLRepository(session)
        self.auth_states = OAuthProviderStateSQLRepository(session)
        self.auth_tokens = OAuthProviderTokenSQLRepository(session)
        self.tracks = TrackSQLRepository(session)
        self.taste_profiles = TasteProfileSQLRepository(session)
        self.blacklist = BlacklistSQLRepository(session)
        self.playlists = PlaylistSQLRepository(session)

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._get_session()
        try:
            if exc is not None:
                await session.rollback()
            elif not self.rolled_back:
                await session.commit()
        finally:
            await session.close()
            self.session = None

    async def rollback(self) -> None:
        await self._get_session().rollback()
        self.rolled_back = True

    def _get_session(self) -> AsyncSession:
        if self.session is None:
            raise RuntimeError("No unit of work block is open")
        return self.session
