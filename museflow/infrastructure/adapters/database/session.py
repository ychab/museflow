from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from museflow.infrastructure.config.settings.database import database_settings


def create_engine(url: str, idle_in_transaction_timeout: int, pool_size: int, max_overflow: int) -> AsyncEngine:
    return create_async_engine(
        url=url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        # A pooled connection may have died since its last use (database restart, network cut, idle timeout): a cheap
        # ping on checkout replaces it, instead of failing the first query of a request.
        pool_pre_ping=True,
        # PostgreSQL terminates a session left idle in a transaction (value in ms): a remote call inside a unit of
        # work block fails loudly instead of holding locks and a connection.
        connect_args={
            "server_settings": {"idle_in_transaction_session_timeout": str(idle_in_transaction_timeout * 1000)},
        },
    )


if database_settings.URI is None:
    raise RuntimeError("Did you forget to export DATABASE_ env vars?")

async_engine: AsyncEngine = create_engine(
    str(database_settings.URI),
    idle_in_transaction_timeout=database_settings.IDLE_IN_TRANSACTION_TIMEOUT,
    pool_size=database_settings.POOL_SIZE,
    max_overflow=database_settings.MAX_OVERFLOW,
)
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    # Prevent attributes from being expired after commit/transaction for async DB.
    # @see https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.expire_on_commit
    expire_on_commit=False,
    autoflush=False,  # Require explicit .flush() in transaction to see changes
    autocommit=False,  # Require explicit .commit() in transaction to see changes
)
