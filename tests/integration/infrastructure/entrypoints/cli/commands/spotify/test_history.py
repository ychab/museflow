from collections.abc import Iterable
from pathlib import Path
from unittest import mock

import pytest

from museflow.application.inputs.history import ImportStreamingHistoryConfigInput
from museflow.application.use_cases.import_streaming_history import ImportStreamingHistoryReport
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.infrastructure.entrypoints.cli.commands.spotify.history import history_logic


class TestSpotifyHistoryLogic:
    """
    The purpose of this test is to check that the user and the auth token are loaded correctly.
    Otherwise, we trust use case integration tests and prevent duplicate.
    """

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.history.ImportStreamingHistoryUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = mock.AsyncMock()
            yield patched.return_value

    async def test__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        mock_use_case: mock.AsyncMock,
        tmp_path: Path,
    ) -> None:
        mock_use_case.import_history.return_value = ImportStreamingHistoryReport(
            items_read=1000,
            items_skipped_no_ts=5,
            items_skipped_duration=200,
            items_skipped_no_uri=50,
            unique_track_ids=750,
            tracks_already_known=300,
            tracks_fetched=450,
            tracks_created=200,
        )

        report = await history_logic(
            email=user.email,
            config=ImportStreamingHistoryConfigInput(directory=tmp_path),
        )

        assert report.items_read == 1000
        assert report.items_skipped_no_ts == 5
        assert report.items_skipped_duration == 200
        assert report.items_skipped_no_uri == 50
        assert report.unique_track_ids == 750
        assert report.tracks_already_known == 300
        assert report.tracks_fetched == 450
        assert report.tracks_created == 200
