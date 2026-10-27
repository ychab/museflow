from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from museflow.application.ports.unit_of_work import UnitOfWorkPort

ATOMIC_SESSION_KEY = "museflow_atomic"


class SQLUnitOfWork(UnitOfWorkPort):
    """Unit of work on top of repositories that commit on their own.

    Repositories call `session.commit()` after each mutation. Rather than changing all of them, the block swaps
    `commit` for `flush` on this session: each write still sends its SQL, but the transaction stays open until the
    block exits.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @asynccontextmanager
    async def atomic(self) -> AsyncGenerator[None]:
        # Nesting would restore `flush` as `commit` at the inner exit and leave the session broken.
        if self.session.info.get(ATOMIC_SESSION_KEY):
            raise RuntimeError("A unit of work block is already open on this session")

        commit = self.session.commit
        self.session.info[ATOMIC_SESSION_KEY] = True
        self.session.commit = self.session.flush  # type: ignore[method-assign]

        try:
            yield
        except:
            await self.session.rollback()
            raise
        else:
            await commit()
        finally:
            self.session.commit = commit  # type: ignore[method-assign]
            del self.session.info[ATOMIC_SESSION_KEY]
