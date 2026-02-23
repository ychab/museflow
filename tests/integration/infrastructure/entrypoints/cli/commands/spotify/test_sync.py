from collections.abc import Iterable
from unittest import mock

import pytest

from spotifagent.application.use_cases.provider_sync_music import SyncConfig
from spotifagent.application.use_cases.provider_sync_music import SyncReport
from spotifagent.domain.entities.auth import OAuthProviderUserToken
from spotifagent.domain.entities.music import MusicProvider
from spotifagent.domain.entities.users import User
from spotifagent.infrastructure.entrypoints.cli.commands.spotify import sync_logic


class TestSpotifySyncLogic:
    """
    The purpose of this test is to check that the user repository is loading
    as expected. Otherwise, we trust use case integration tests and prevent duplicate.
    """

    @pytest.fixture
    def mock_spotify_sync(self) -> Iterable[mock.AsyncMock]:
        target_path = "spotifagent.infrastructure.entrypoints.cli.commands.spotify.sync.sync_music"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    async def test__sync__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        mock_spotify_sync: mock.AsyncMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        mock_spotify_sync.return_value = SyncReport(
            artist_created=100,
            artist_updated=250,
            track_created=100,
            track_updated=250,
        )

        report = await sync_logic(email=user.email, provider=MusicProvider.SPOTIFY, config=SyncConfig(sync=True))

        assert report.artist_created == 100
        assert report.artist_updated == 250
        assert report.track_created == 100
        assert report.track_updated == 250
