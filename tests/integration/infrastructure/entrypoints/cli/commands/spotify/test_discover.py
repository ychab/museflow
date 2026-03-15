from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.use_cases.advisor_discover import DiscoveryConfigInput
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.types import MusicAdvisor
from museflow.infrastructure.entrypoints.cli.commands.spotify.discover import discover_logic

from tests.unit.factories.entities.music import PlaylistFactory


class TestSpotifyDiscoverLogic:
    """
    The purpose of this test is to check that the user and the auth token are loaded correctly.
    Otherwise, we trust to use case integration tests and prevent duplicate.
    """

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.discover.AdvisorDiscoverUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    async def test__discover__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        mock_use_case: mock.Mock,
    ) -> None:
        new_playlist = PlaylistFactory.build(user_id=user.id)
        mock_use_case.create_suggestions_playlist.return_value = new_playlist

        playlist = await discover_logic(
            email=user.email,
            advisor=MusicAdvisor.LASTFM,
            config=DiscoveryConfigInput(),
        )

        assert playlist == new_playlist
