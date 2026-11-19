import uuid
from abc import ABC
from abc import abstractmethod


class FileStoragePort(ABC):
    """Files kept for a user between their upload and their processing, e.g. a streaming history export.

    Every key belongs to one user: the storage keeps each user's files apart, so a caller can never reach another
    user's file. A key is a relative path (`history/<batch>/file.json`), with `/` as the separator.
    """

    @abstractmethod
    async def put(self, user_id: uuid.UUID, key: str, content: bytes) -> None:
        """Writes the file, replacing any file with the same key."""

    @abstractmethod
    async def get(self, user_id: uuid.UUID, key: str) -> bytes:
        """Reads the file.

        Raises:
            FileStorageKeyNotFoundError: If no file has this key.
        """

    @abstractmethod
    async def list_keys(self, user_id: uuid.UUID, prefix: str) -> list[str]:
        """The keys under the prefix, sorted; none when the prefix holds no file."""

    @abstractmethod
    async def delete(self, user_id: uuid.UUID, prefix: str) -> int:
        """Deletes every file under the prefix and returns how many were deleted."""
