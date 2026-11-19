import uuid
from pathlib import Path

import pytest

from museflow.infrastructure.adapters.storage.local import LocalFileStorage


class TestLocalFileStorage:
    @pytest.fixture
    def file_storage(self, tmp_path: Path) -> LocalFileStorage:
        return LocalFileStorage(root=tmp_path / "storage")

    @pytest.mark.parametrize(
        "key",
        [
            pytest.param("", id="empty"),
            pytest.param("/etc/passwd", id="absolute"),
            pytest.param("../other/a.json", id="parent"),
            pytest.param("history/../../other/a.json", id="parent_nested"),
        ],
    )
    async def test__key__invalid(self, file_storage: LocalFileStorage, key: str) -> None:
        with pytest.raises(ValueError, match="Invalid storage key"):
            await file_storage.put(user_id=uuid.uuid4(), key=key, content=b"[]")

    async def test__prefix__empty__every_file_of_the_user(self, file_storage: LocalFileStorage) -> None:
        user_id = uuid.uuid4()
        await file_storage.put(user_id=user_id, key="a.json", content=b"[]")

        assert await file_storage.list_keys(user_id=user_id, prefix="") == ["a.json"]

    async def test__key__symbolic_link_outside(self, file_storage: LocalFileStorage, tmp_path: Path) -> None:
        user_id = uuid.uuid4()
        user_root = tmp_path / "storage" / str(user_id)
        user_root.mkdir(parents=True)
        (user_root / "escape").symlink_to(tmp_path)

        with pytest.raises(ValueError, match="Invalid storage key"):
            await file_storage.get(user_id=user_id, key="escape/a.json")
