from collections.abc import Iterable
from pathlib import Path
from typing import Final
from unittest import mock

import pytest

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.use_cases.track_history_import import ImportStreamingHistoryReport
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.progress.rich import RichProgressAdapter
from museflow.infrastructure.adapters.storage.local import LocalFileStorage
from museflow.infrastructure.entrypoints.cli.commands.tracks.history import tracks_history_logic

from tests import ASSETS_DIR

HISTORY_DIR: Final[Path] = ASSETS_DIR / "history" / "spotify" / "samples"


class TestTracksHistoryLogic:
    """
    The purpose of this test is to check that the user is loaded and the export files go through the user's file
    storage. Otherwise, we trust use case integration tests and prevent duplicate.
    """

    PREFIX: Final[str] = "history/batch"

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.tracks.history.ImportStreamingHistoryUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = mock.AsyncMock()
            yield patched.return_value

    async def test__nominal(
        self,
        user: User,
        mock_use_case: mock.AsyncMock,
        file_storage: LocalFileStorage,
        progress: RichProgressAdapter,
    ) -> None:
        keys_during_import: list[str] = []

        async def import_history(
            user: User, config: ImportStreamingHistoryConfigInput
        ) -> ImportStreamingHistoryReport:
            keys_during_import.extend(await file_storage.list_keys(user_id=user.id, prefix=config.prefix))
            return ImportStreamingHistoryReport(items_read=6)

        mock_use_case.import_history.side_effect = import_history

        report = await tracks_history_logic(
            progress=progress,
            email=user.email,
            directory=HISTORY_DIR,
            config=ImportStreamingHistoryConfigInput(prefix=self.PREFIX),
            provider=MusicProvider.SPOTIFY,
        )

        assert report.items_read == 6
        # The export files were in the user's storage during the import, and are deleted after it
        assert keys_during_import == [f"{self.PREFIX}/{path.name}" for path in sorted(HISTORY_DIR.iterdir())]
        assert await file_storage.list_keys(user_id=user.id, prefix=self.PREFIX) == []

    async def test__archive__nominal(
        self,
        user: User,
        mock_use_case: mock.AsyncMock,
        zip_archive: bytes,
        file_storage: LocalFileStorage,
        progress: RichProgressAdapter,
        tmp_path: Path,
    ) -> None:
        archive = tmp_path / "my_spotify_data.zip"
        archive.write_bytes(zip_archive)
        keys_during_import: list[str] = []

        async def import_history(
            user: User, config: ImportStreamingHistoryConfigInput
        ) -> ImportStreamingHistoryReport:
            keys_during_import.extend(await file_storage.list_keys(user_id=user.id, prefix=config.prefix))
            return ImportStreamingHistoryReport(items_read=6)

        mock_use_case.import_history.side_effect = import_history

        report = await tracks_history_logic(
            progress=progress,
            email=user.email,
            archive=archive,
            config=ImportStreamingHistoryConfigInput(prefix=self.PREFIX),
            provider=MusicProvider.SPOTIFY,
        )

        assert report.items_read == 6
        # The files extracted from the archive were in the user's storage during the import, and are deleted after it
        assert keys_during_import == [
            f"{self.PREFIX}/{rank}/{path.name}" for rank, path in enumerate(sorted(HISTORY_DIR.iterdir()))
        ]
        assert await file_storage.list_keys(user_id=user.id, prefix=self.PREFIX) == []
