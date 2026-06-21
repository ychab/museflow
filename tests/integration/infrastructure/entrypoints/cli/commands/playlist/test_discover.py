from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.inputs.discovery import DiscoverTasteConfigInput
from museflow.application.use_cases.taste_discover import DiscoverTasteResult
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.types import MusicAdvisor
from museflow.domain.types import MusicProvider
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy
from museflow.infrastructure.entrypoints.cli.commands.playlist.discover import discover_logic

from tests.unit.factories.entities.music import PlaylistFactory


class TestDiscoverLogic:
    """
    The purpose of this test is to check that the user and the auth token are loaded correctly.
    Otherwise, we trust use case integration tests and avoid duplication.
    """

    @pytest.fixture
    def mock_use_case(self) -> Iterable[mock.Mock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.playlist.discover.DiscoverTasteUseCase"
        with mock.patch(target_path, autospec=True) as patched:
            yield patched.return_value

    @pytest.mark.parametrize("advisor", list(MusicAdvisor))
    async def test__discover__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        advisor: MusicAdvisor,
        discovery_taste_strategy: DiscoveryTasteStrategy,
        mock_use_case: mock.Mock,
    ) -> None:
        expected_result = DiscoverTasteResult(
            provider_playlist=PlaylistFactory.build(user_id=user.id),
            discovery_playlist=None,
            strategy=discovery_taste_strategy,
            reports=[],
            tracks=[],
        )
        mock_use_case.create_suggestions_playlist.return_value = expected_result

        result = await discover_logic(
            email=user.email,
            advisor=advisor,
            provider=MusicProvider.SPOTIFY,
            config=DiscoverTasteConfigInput(),
        )

        assert result == expected_result
