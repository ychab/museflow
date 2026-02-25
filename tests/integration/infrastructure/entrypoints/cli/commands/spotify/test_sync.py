from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.use_cases.provider_sync_library import SyncConfig
from museflow.application.use_cases.provider_sync_library import SyncReport
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.users import User
from museflow.infrastructure.entrypoints.cli.commands.spotify.sync import sync_logic


class TestSpotifySyncLogic:
    """
    The purpose of this test is to check that the user and the auth token are loaded correctly.
    Otherwise, we trust use case integration tests and prevent duplicate.
    """

    @pytest.fixture
    def mock_spotify_sync(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.sync.ProviderSyncLibraryUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    async def test__sync__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        mock_spotify_sync: mock.Mock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        mock_spotify_sync.execute.return_value = SyncReport(
            artist_created=100,
            artist_updated=250,
            track_created=100,
            track_updated=250,
        )

        report = await sync_logic(email=user.email, config=SyncConfig(sync_all=True))

        assert report.artist_created == 100
        assert report.artist_updated == 250
        assert report.track_created == 100
        assert report.track_updated == 250
