from abc import ABC
from abc import abstractmethod
from types import TracebackType
from typing import Self

from museflow.application.ports.repositories.auth import OAuthProviderStateRepository
from museflow.application.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.application.ports.repositories.blacklist import BlacklistRepository
from museflow.application.ports.repositories.playlist import PlaylistRepository
from museflow.application.ports.repositories.taste import TasteProfileRepository
from museflow.application.ports.repositories.track import TrackRepository
from museflow.application.ports.repositories.users import UserRepository


class UnitOfWorkPort(ABC):
    """Port for one short transaction per `async with` block.

    Entering the block opens a transaction and gives access to the repositories. A clean exit commits, an exception
    rolls back, and the transaction never outlives the block. Keep remote calls (providers, advisors) out of the
    block, so no connection waits on them. Blocks don't nest, and one instance serves one flow at a time.
    """

    users: UserRepository
    auth_states: OAuthProviderStateRepository
    auth_tokens: OAuthProviderTokenRepository
    tracks: TrackRepository
    taste_profiles: TasteProfileRepository
    blacklist: BlacklistRepository
    playlists: PlaylistRepository

    @abstractmethod
    async def __aenter__(self) -> Self:
        """Open the transaction.

        Raises:
            RuntimeError: If a block is already open on this instance.
        """
        ...

    @abstractmethod
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    @abstractmethod
    async def rollback(self) -> None:
        """Discard the writes made so far in the block; the block then exits without committing."""
        ...
