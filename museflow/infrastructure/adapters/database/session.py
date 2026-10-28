from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from museflow.infrastructure.config.settings.database import database_settings

if database_settings.URI is None:
    raise RuntimeError("Did you forget to export DATABASE_ env vars?")

async_engine: AsyncEngine = create_async_engine(url=str(database_settings.URI))
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    # Prevent attributes from being expired after commit/transaction for async DB.
    # @see https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.expire_on_commit
    expire_on_commit=False,
    autoflush=False,  # Require explicit .flush() in transaction to see changes
    autocommit=False,  # Require explicit .commit() in transaction to see changes
)
