import uuid
from pathlib import Path

import pytest

from museflow.domain.entities.user import User
from museflow.domain.exceptions import FileStorageKeyNotFoundError
from museflow.infrastructure.adapters.storage.local import LocalFileStorage


class TestLocalFileStorage:
    async def test__nominal(self, user: User, file_storage: LocalFileStorage, file_storage_dir: Path) -> None:
        await file_storage.put(user_id=user.id, key="history/batch/b.json", content=b"[2]")
        await file_storage.put(user_id=user.id, key="history/batch/a.json", content=b"[1]")
        await file_storage.put(user_id=user.id, key="history/other/c.json", content=b"[3]")

        assert (file_storage_dir / str(user.id) / "history" / "batch" / "a.json").read_bytes() == b"[1]"
        assert await file_storage.get(user_id=user.id, key="history/batch/a.json") == b"[1]"
        assert await file_storage.list_keys(user_id=user.id, prefix="history/batch") == [
            "history/batch/a.json",
            "history/batch/b.json",
        ]

        assert await file_storage.delete(user_id=user.id, prefix="history/batch") == 2
        assert await file_storage.list_keys(user_id=user.id, prefix="history") == ["history/other/c.json"]

    async def test__put__replaces(self, user: User, file_storage: LocalFileStorage) -> None:
        await file_storage.put(user_id=user.id, key="history/a.json", content=b"[1]")
        await file_storage.put(user_id=user.id, key="history/a.json", content=b"[2]")

        assert await file_storage.get(user_id=user.id, key="history/a.json") == b"[2]"

    async def test__users__isolated(self, user: User, file_storage: LocalFileStorage) -> None:
        other_user_id = uuid.uuid4()
        await file_storage.put(user_id=other_user_id, key="history/a.json", content=b"[1]")

        assert await file_storage.list_keys(user_id=user.id, prefix="history") == []
        assert await file_storage.delete(user_id=user.id, prefix="history") == 0
        with pytest.raises(FileStorageKeyNotFoundError):
            await file_storage.get(user_id=user.id, key="history/a.json")

        assert await file_storage.list_keys(user_id=other_user_id, prefix="history") == ["history/a.json"]

    async def test__get__not_found(self, user: User, file_storage: LocalFileStorage) -> None:
        with pytest.raises(FileStorageKeyNotFoundError, match="No file found for key: history/a.json"):
            await file_storage.get(user_id=user.id, key="history/a.json")
