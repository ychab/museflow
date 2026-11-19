import asyncio
from collections.abc import Coroutine
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.infrastructure.adapters.database.session import create_engine_from_settings
from museflow.infrastructure.adapters.database.session import create_session_factory
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork

# The database of the running command, open between the start and the end of `init_logic_runner`.
session_factory: async_sessionmaker[AsyncSession] | None = None


# --- Event loop ---


def run_logic[T](main: Coroutine[Any, Any, T]) -> T:
    """Runs a command's logic like `asyncio.run`, with the database open for the run."""
    with init_logic_runner() as runner:
        result = runner.run(main)
    return result


@contextmanager
def init_logic_runner() -> Iterator[asyncio.Runner]:
    """An `asyncio.Runner` with the database open, for a command that prints between two steps of its logic.

    The engine is created in the runner's event loop, which its pooled connections are bound to, and disposed of in
    that loop when the command ends: a second loop could not reuse them.
    """
    global session_factory

    with asyncio.Runner() as runner:
        engine = create_engine_from_settings()
        session_factory = create_session_factory(engine)
        try:
            yield runner
        finally:
            session_factory = None
            runner.run(engine.dispose())


# --- Unit of work ---


def get_unit_of_work() -> UnitOfWorkPort:
    """The unit of work of the running command.

    Raises:
        RuntimeError: If the command runs its logic without `run_logic` or `init_logic_runner`.
    """
    if session_factory is None:
        raise RuntimeError("No database open: run the command logic through run_logic()")
    return SQLUnitOfWork(session_factory)
