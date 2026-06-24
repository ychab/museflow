import re
import uuid
from datetime import date
from unittest import mock

import pytest

from museflow.application.inputs.playlist import PlaylistHistoryConfigInput
from museflow.application.use_cases.playlist_history import playlist_history
from museflow.domain.exceptions import PlaylistNoTracksError
from museflow.domain.types import PlaylistHistoryOrderBy
from museflow.domain.types import PlaylistType
from museflow.domain.types import SortOrder
from museflow.domain.types import TrackOrderBy

from tests.unit.factories.entities.track import TrackFactory
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

    async def test__group_by_artists__played_count(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        # Artist B has max played_count=8, Artist A has max played_count=5 — Artist B should come first.
        track_a1 = TrackFactory.build(artists=["Artist A"], played_count=5)
        track_a2 = TrackFactory.build(artists=["Artist A"], played_count=3)
        track_b1 = TrackFactory.build(artists=["Artist B"], played_count=8)
        # DB returns tracks already sorted by played_count DESC
        mock_track_repository.get_list.return_value = [track_b1, track_a1, track_a2]
        playlist = mock_provider_library.create_playlist.return_value
        mock_playlist_repository.save.return_value = playlist

        await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(group_by_artists=True),
            track_repository=mock_track_repository,
            playlist_repository=mock_playlist_repository,
            provider_library=mock_provider_library,
        )

        call_tracks = mock_provider_library.create_playlist.call_args.kwargs["tracks"]
        assert call_tracks == [track_b1, track_a1, track_a2]

    async def test__group_by_artists__score(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        # Artist B has max score=9, Artist A has max score=7, Artist C has no score (→ -1).
        track_b1 = TrackFactory.build(artists=["Artist B"], score=9)
        track_a1 = TrackFactory.build(artists=["Artist A"], score=7)
        track_a2 = TrackFactory.build(artists=["Artist A"], score=5)
        track_c1 = TrackFactory.build(artists=["Artist C"], score=None)
        # DB returns tracks sorted by score DESC NULLS LAST
        mock_track_repository.get_list.return_value = [track_b1, track_a1, track_a2, track_c1]
        playlist = mock_provider_library.create_playlist.return_value
        mock_playlist_repository.save.return_value = playlist

        await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(sort_by=PlaylistHistoryOrderBy.SCORE, group_by_artists=True),
            track_repository=mock_track_repository,
            playlist_repository=mock_playlist_repository,
            provider_library=mock_provider_library,
        )

        call_tracks = mock_provider_library.create_playlist.call_args.kwargs["tracks"]
        assert call_tracks == [track_b1, track_a1, track_a2, track_c1]

    async def test__playlist_name__custom(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        mock_track_repository.get_list.return_value = [TrackFactory.build()]
        playlist = mock_provider_library.create_playlist.return_value
        mock_playlist_repository.save.return_value = playlist

        await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(name_suffix="My Mix"),
            track_repository=mock_track_repository,
            playlist_repository=mock_playlist_repository,
            provider_library=mock_provider_library,
        )

        name = mock_provider_library.create_playlist.call_args.kwargs["name"]
        assert name == "[Museflow] - History - My Mix"

    async def test__playlist_name__default__seconds_only(
        self,
        mock_track_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        mock_track_repository.get_list.return_value = [TrackFactory.build()]
        playlist = mock_provider_library.create_playlist.return_value
        mock_playlist_repository.save.return_value = playlist

        await playlist_history(
            user=user,
            config=PlaylistHistoryConfigInput(),
            track_repository=mock_track_repository,
            playlist_repository=mock_playlist_repository,
            provider_library=mock_provider_library,
        )

        name = mock_provider_library.create_playlist.call_args.kwargs["name"]
        assert re.fullmatch(r"\[Museflow\] - History - \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00", name)

    async def test__date_filters__forwarded_to_repository(
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
                config=PlaylistHistoryConfigInput(
                    played_first_min=date(2025, 1, 1),
                    played_first_max=date(2025, 12, 31),
                    played_last_min=date(2026, 1, 1),
                    played_last_max=date(2026, 12, 31),
                ),
                track_repository=mock_track_repository,
                playlist_repository=mock_playlist_repository,
                provider_library=mock_provider_library,
            )

        kwargs = mock_track_repository.get_list.call_args.kwargs
        assert kwargs["played_first_min"] == date(2025, 1, 1)
        assert kwargs["played_first_max"] == date(2025, 12, 31)
        assert kwargs["played_last_min"] == date(2026, 1, 1)
        assert kwargs["played_last_max"] == date(2026, 12, 31)

    async def test__sort_by_score__flat(
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
                config=PlaylistHistoryConfigInput(sort_by=PlaylistHistoryOrderBy.SCORE),
                track_repository=mock_track_repository,
                playlist_repository=mock_playlist_repository,
                provider_library=mock_provider_library,
            )

        assert mock_track_repository.get_list.call_args.kwargs["order"] == [(TrackOrderBy.SCORE, SortOrder.DESC)]
        mock_provider_library.create_playlist.assert_not_awaited()
