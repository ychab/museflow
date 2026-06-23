import uuid
from unittest import mock

import pytest

from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.application.use_cases.playlist_history import playlist_history
from museflow.domain.exceptions import PlaylistNoTracksError
from museflow.domain.types import PlaylistType

from tests.unit.factories.entities.user import UserFactory


class TestPlaylistHistoryUseCase:
    async def test__no_tracks_found__dedup_enabled__raises(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        excluded_id = uuid.uuid4()
        mock_playlist_repository.get_track_ids.return_value = frozenset({excluded_id})
        mock_track_repository.get_list.return_value = []

        with pytest.raises(PlaylistNoTracksError):
            await playlist_history(
                user=user,
                config=PlaylistHistoryConfigInput(),
                track_repository=mock_track_repository,
                playlist_repository=mock_playlist_repository,
                provider_library=mock_provider_library,
            )

        mock_playlist_repository.get_track_ids.assert_awaited_once_with(user.id, type=PlaylistType.HISTORY)
        assert mock_track_repository.get_list.call_args.kwargs["exclude_ids"] == [excluded_id]
        mock_provider_library.create_playlist.assert_not_awaited()

    async def test__no_tracks_found__duplicates_allowed__skips_dedup_lookup(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        mock_track_repository.get_list.return_value = []

        with pytest.raises(PlaylistNoTracksError):
            await playlist_history(
                user=user,
                config=PlaylistHistoryConfigInput(allow_duplicate=True),
                track_repository=mock_track_repository,
                playlist_repository=mock_playlist_repository,
                provider_library=mock_provider_library,
            )

        mock_playlist_repository.get_track_ids.assert_not_awaited()
        assert mock_track_repository.get_list.call_args.kwargs["exclude_ids"] is None
