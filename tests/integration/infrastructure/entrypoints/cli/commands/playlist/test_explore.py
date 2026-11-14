from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.inputs.explore import ExploreArtistsConfigInput
from museflow.application.use_cases.artists_explore import ExploreArtistsResult
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.playlist.explore import playlist_explore_logic

from tests.unit.factories.entities.playlist import PlaylistFactory


@pytest.mark.wiremock("openrouter")
@pytest.mark.usefixtures("openrouter_settings_wiremock")
class TestPlaylistExploreLogic:
    """Checks that the user and the auth token are loaded; the use case integration tests cover the rest."""

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.playlist.explore.ExploreArtistsUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    async def test__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        mock_use_case: mock.Mock,
    ) -> None:
        expected_result = ExploreArtistsResult(playlist=PlaylistFactory.build(user_id=user.id), reports=[], tracks=[])
        mock_use_case.create_playlist.return_value = expected_result

        result = await playlist_explore_logic(
            email=user.email,
            provider=MusicProvider.SPOTIFY,
            config=ExploreArtistsConfigInput(),
            # The default advisor model is missing from the WireMock catalog: the check passes only with the override
            model="google/gemini-3.5-flash",
        )

        assert result == expected_result
