from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.inputs.discovery import DiscoverySimilarConfigInput
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.types import MusicAdvisorSimilar
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.discover.similar import discover_similar_logic

from tests.unit.factories.entities.music import PlaylistFactory


class TestDiscoverSimilarLogic:
    """
    The purpose of this test is to check that the user and the auth token are loaded correctly.
    Otherwise, we trust to use case integration tests and prevent duplicate.
    """

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.discover.similar.DiscoverSimilarUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    @pytest.mark.parametrize("advisor", list(MusicAdvisorSimilar))
    async def test__discover__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        advisor: MusicAdvisorSimilar,
        mock_use_case: mock.Mock,
    ) -> None:
        new_playlist = PlaylistFactory.build(user_id=user.id)
        mock_use_case.create_suggestions_playlist.return_value = new_playlist

        playlist = await discover_similar_logic(
            email=user.email,
            advisor=advisor,
            provider=MusicProvider.SPOTIFY,
            config=DiscoverySimilarConfigInput(),
        )

        assert playlist == new_playlist
