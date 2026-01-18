from collections.abc import Iterable
from unittest import mock

import pytest

from spotifagent.application.use_cases.spotify_sync_top_items import SyncReport
from spotifagent.domain.entities.users import User
from spotifagent.infrastructure.entrypoints.cli.commands.spotify import sync_top_items_logic


class TestSpotifySyncTopItemsLogic:
    """
    The purpose of this test is to check that the user repository is loading
    as expected. Otherwise, we trust use case integration tests and prevent duplicate.
    """

    @pytest.fixture
    def mock_spotify_sync_top_items(self) -> Iterable[mock.AsyncMock]:
        target_path = (
            "spotifagent.infrastructure.entrypoints.cli.commands.spotify.sync_top_items.spotify_sync_top_items"
        )
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    async def test__nominal(
        self,
        user: User,
        mock_spotify_sync_top_items: mock.AsyncMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        mock_spotify_sync_top_items.return_value = SyncReport(top_artist_created=100, top_artist_updated=250)

        await sync_top_items_logic(user.email, sync_top_artists=True)

        captured = capsys.readouterr()
        assert "Synchronization successful!" in captured.out
        assert "- 100 top artists created" in captured.out
        assert "- 250 top artists updated" in captured.out
