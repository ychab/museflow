import asyncio
import shutil
import uuid
from pathlib import Path
from pathlib import PurePosixPath

from museflow.application.ports.storage import FileStoragePort
from museflow.domain.exceptions import FileStorageKeyNotFoundError


class LocalFileStorage(FileStoragePort):
    """Stores each user's files under `<root>/<user_id>/<key>`, on a disk (a volume shared by the processes)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    async def put(self, user_id: uuid.UUID, key: str, content: bytes) -> None:
        path = self._resolve(user_id, key)
        await asyncio.to_thread(self._write, path, content)

    async def get(self, user_id: uuid.UUID, key: str) -> bytes:
        path = self._resolve(user_id, key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as e:
            raise FileStorageKeyNotFoundError(f"No file found for key: {key}") from e

    async def list_keys(self, user_id: uuid.UUID, prefix: str) -> list[str]:
        user_root = self._user_root(user_id)
        directory = self._resolve(user_id, prefix, allow_empty=True)
        paths = await asyncio.to_thread(self._files, directory)
        return sorted(path.relative_to(user_root).as_posix() for path in paths)

    async def delete(self, user_id: uuid.UUID, prefix: str) -> int:
        directory = self._resolve(user_id, prefix, allow_empty=True)
        return await asyncio.to_thread(self._delete_tree, directory)

    def _user_root(self, user_id: uuid.UUID) -> Path:
        return (self._root / str(user_id)).resolve()

    def _resolve(self, user_id: uuid.UUID, key: str, allow_empty: bool = False) -> Path:
        """The path of the key, inside the user's directory.

        Raises:
            ValueError: If the key is empty (unless allowed), absolute, or climbs out of the user's directory.
        """
        relative = PurePosixPath(key)
        if relative.is_absolute() or ".." in relative.parts or (not relative.parts and not allow_empty):
            raise ValueError(f"Invalid storage key: {key!r}")

        user_root = self._user_root(user_id)
        path = (user_root / relative).resolve()
        if not path.is_relative_to(user_root):  # a symbolic link pointing outside
            raise ValueError(f"Invalid storage key: {key!r}")
        return path

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    @staticmethod
    def _files(directory: Path) -> list[Path]:
        if not directory.is_dir():
            return []
        return [path for path in directory.rglob("*") if path.is_file()]

    @classmethod
    def _delete_tree(cls, directory: Path) -> int:
        count = len(cls._files(directory))
        if directory.is_dir():
            shutil.rmtree(directory)
        return count
