from collections.abc import Iterator
from unittest import mock

import pytest

from museflow.application.inputs.history import ImportStreamingHistoryJobInput
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.entrypoints.worker.tasks.track import track_history_import_work

from tests.unit.factories.entities.job import JobFactory

TARGET_PATH = "museflow.infrastructure.entrypoints.worker.tasks.track"


class TestTrackHistoryImportWork:
    @pytest.fixture
    def mock_get_wiring(self, mock_file_storage: mock.AsyncMock) -> Iterator[mock.Mock]:
        with mock.patch(f"{TARGET_PATH}.get_wiring") as patched:
            patched.return_value.build_file_storage.return_value = mock_file_storage
            yield patched

    @pytest.fixture
    def mock_get_user_by_id(self) -> Iterator[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.get_user_by_id", new_callable=mock.AsyncMock) as patched:
            yield patched

    async def test__transient_error__files_kept(
        self,
        mock_get_wiring: mock.Mock,
        mock_get_user_by_id: mock.AsyncMock,
        mock_file_storage: mock.AsyncMock,
    ) -> None:
        mock_get_user_by_id.side_effect = ConnectionError("The database is unreachable")
        job_in = ImportStreamingHistoryJobInput(prefix="history/1", provider=MusicProvider.SPOTIFY)
        job = JobFactory.build(input=job_in.model_dump(mode="json"))

        with pytest.raises(ConnectionError):
            await track_history_import_work(job)

        # The next try extracts the archive again
        mock_file_storage.delete.assert_not_awaited()
