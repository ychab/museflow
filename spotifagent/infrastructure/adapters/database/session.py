from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from spotifagent.infrastructure.config.settings.database import database_settings

assert database_settings.URI is not None, "Did you forgot to export DATABASE_ env vars?"

async_engine: AsyncEngine = create_async_engine(url=str(database_settings.URI))
async_session_factory: async_sessionmaker = async_sessionmaker(
    bind=async_engine,
    # Prevent attributes from being expired after commit/transaction for async DB.
    # @see https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.expire_on_commit
    expire_on_commit=False,
    autoflush=False,  # Require explicit .flush() in transaction to see changes
    autocommit=False,  # Require explicit .commit() in transaction to see changes
)


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession]:
    db_session: AsyncSession = async_session_factory()

    try:
        yield db_session
    except:
        await db_session.rollback()
        raise
    finally:
        await db_session.close()
