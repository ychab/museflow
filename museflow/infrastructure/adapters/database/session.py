from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from museflow.infrastructure.config.settings.database import database_settings


def create_engine(url: str, idle_in_transaction_timeout: int) -> AsyncEngine:
    return create_async_engine(
        url=url,
        # PostgreSQL terminates a session left idle in a transaction (value in ms): a remote call inside a unit of
        # work block fails loudly instead of holding locks and a connection.
        connect_args={
            "server_settings": {"idle_in_transaction_session_timeout": str(idle_in_transaction_timeout * 1000)},
        },
    )


if database_settings.URI is None:
    raise RuntimeError("Did you forget to export DATABASE_ env vars?")

async_engine: AsyncEngine = create_engine(str(database_settings.URI), database_settings.IDLE_IN_TRANSACTION_TIMEOUT)
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    # Prevent attributes from being expired after commit/transaction for async DB.
    # @see https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.expire_on_commit
    expire_on_commit=False,
    autoflush=False,  # Require explicit .flush() in transaction to see changes
    autocommit=False,  # Require explicit .commit() in transaction to see changes
)
