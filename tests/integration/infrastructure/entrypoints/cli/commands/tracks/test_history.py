from collections.abc import Iterable
from pathlib import Path
from unittest import mock

import pytest

from museflow.application.inputs.history import StreamingHistoryImportConfigInput
from museflow.application.use_cases.history_import import ImportStreamingHistoryReport
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.tracks.history import history_logic


class TestHistoryLogic:
    """
    The purpose of this test is to check that the user and the auth token are loaded correctly.
    Otherwise, we trust use case integration tests and prevent duplicate.
    """

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
        tmp_path: Path,
    ) -> None:
        mock_use_case.import_history.return_value = ImportStreamingHistoryReport(
            items_read=1000,
            items_skipped_no_timestamp=5,
            items_skipped_short_play=200,
            items_skipped_no_track_id=50,
            unique_track_ids=750,
            tracks_already_known=300,
            tracks_created=200,
        )

        report = await history_logic(
            email=user.email,
            config=StreamingHistoryImportConfigInput(directory=tmp_path),
            provider=MusicProvider.SPOTIFY,
        )

        assert report.items_read == 1000
        assert report.items_skipped_no_timestamp == 5
        assert report.items_skipped_short_play == 200
        assert report.items_skipped_no_track_id == 50
        assert report.unique_track_ids == 750
        assert report.tracks_already_known == 300
        assert report.tracks_created == 200
