from abc import ABC
from abc import abstractmethod
from contextlib import AbstractAsyncContextManager


class UnitOfWorkPort(ABC):
    """Port for controlling transactions on top of repositories that commit on their own.

    Repositories commit on their own by default (commit per step). Use `atomic()` only when a partial state would
    be wrong, not merely incomplete, and `release()` before a long remote call that follows a read.
    """

    @abstractmethod
    def atomic(self) -> AbstractAsyncContextManager[None]:
        """Commit the repository writes made in the block once at exit, or roll them all back if it raises.

        Keep remote calls (providers, advisors) out of the block: a write they make on the same session, such as a
        refreshed token, would be committed or rolled back with the block instead of right away.

        Raises:
            RuntimeError: If a block is already open on the same session.
        """
        ...

    @abstractmethod
    async def release(self) -> None:
        """End the open transaction, if any, before a long remote call.

        A read opens a transaction that only the next commit ends: without this call, the connection would stay idle
        in transaction for the whole remote call.

        Raises:
            RuntimeError: If called inside an `atomic()` block.
        """
        ...
