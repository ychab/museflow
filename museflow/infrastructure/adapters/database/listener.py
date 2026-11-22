import logging
from collections.abc import Callable
from types import TracebackType
from typing import Any
from typing import Self

import asyncpg
from sqlalchemy import make_url

logger = logging.getLogger(__name__)


class PostgresListener:
    """Listens to a PostgreSQL channel (`LISTEN`) on a connection of its own, out of the pool: it stays open for
    good, and a pooled connection would go back to the pool between two notifications.

    A notification is lost while no one listens: the caller still polls, the notifications only wake it up sooner.
    `ensure_listening` reconnects after the connection dropped (a database restart).
    """

    def __init__(self, database_uri: str, channel: str, on_notify: Callable[[], None]) -> None:
        # asyncpg takes the plain scheme, without SQLAlchemy's driver suffix
        self._dsn = make_url(database_uri).set(drivername="postgresql").render_as_string(hide_password=False)
        self._channel = channel
        self._on_notify = on_notify
        self._connection: asyncpg.Connection | None = None

    async def __aenter__(self) -> Self:
        await self.ensure_listening()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def ensure_listening(self) -> None:
        """Listens again if the connection dropped; on a failure, the next call tries again."""
        if self._connection is not None and not self._connection.is_closed():
            return

        try:
            self._connection = await asyncpg.connect(self._dsn)
            await self._connection.add_listener(self._channel, self._notify)
        except OSError, asyncpg.PostgresError:
            logger.warning(f"Not listening to {self._channel}, tried again on the next poll", exc_info=True)
            self._connection = None

    def _notify(self, connection: Any, pid: int, channel: str, payload: str) -> None:
        self._on_notify()
