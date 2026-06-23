from collections.abc import Iterable
from unittest import mock

import pytest

from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.types import MusicProvider
from museflow.infrastructure.entrypoints.cli.commands.playlist.history import playlist_history_logic

from tests.unit.factories.entities.playlist import PlaylistFactory


class TestHistoryLogic:
    """
    The purpose of this test is to check that the user and the auth token are loaded correctly.
    Otherwise, we trust use case integration tests (test_playlist_history.py) and avoid duplication.
    """

    @pytest.fixture
    def mock_playlist_history(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.playlist.history.playlist_history_use_case"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    async def test__history__nominal(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        mock_playlist_history: mock.AsyncMock,
    ) -> None:
        expected_playlist = PlaylistFactory.build(user_id=user.id)
        mock_playlist_history.return_value = expected_playlist
        config = PlaylistHistoryConfigInput(limit=5)

        result = await playlist_history_logic(email=user.email, provider=MusicProvider.SPOTIFY, config=config)

        assert result == expected_playlist
        mock_playlist_history.assert_awaited_once()
        call_kwargs = mock_playlist_history.call_args.kwargs
        assert call_kwargs["user"].id == user.id
        assert call_kwargs["config"] == config
