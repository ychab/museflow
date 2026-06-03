import uuid
from unittest import mock

from museflow.application.inputs.discovery import BlacklistChoiceInput
from museflow.application.inputs.discovery import DiscoveryPlaylistRatingInput
from museflow.application.use_cases.discovery_playlist_rate import discovery_playlist_rate

from tests.unit.factories.entities.user import UserFactory


class TestDiscoveryPlaylistRateUseCase:
    async def test__nominal__no_ratings_no_blacklist(
        self,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()

        await discovery_playlist_rate(
            user=user,
            ratings=[],
            blacklist_choices=[],
            discovery_playlist_repository=mock_discovery_playlist_repository,
            blacklist_repository=mock_blacklist_repository,
        )

        mock_discovery_playlist_repository.rate_track.assert_not_awaited()
        mock_blacklist_repository.add_track.assert_not_awaited()
        mock_blacklist_repository.add_artist.assert_not_awaited()

    async def test__rates_tracks(
        self,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        track_id_1 = uuid.uuid4()
        track_id_2 = uuid.uuid4()
        ratings = [
            DiscoveryPlaylistRatingInput(track_id=track_id_1, score=8),
            DiscoveryPlaylistRatingInput(track_id=track_id_2, score=2),
        ]

        await discovery_playlist_rate(
            user=user,
            ratings=ratings,
            blacklist_choices=[],
            discovery_playlist_repository=mock_discovery_playlist_repository,
            blacklist_repository=mock_blacklist_repository,
        )

        assert mock_discovery_playlist_repository.rate_track.await_count == 2
        mock_discovery_playlist_repository.rate_track.assert_any_await(user.id, track_id_1, 8)
        mock_discovery_playlist_repository.rate_track.assert_any_await(user.id, track_id_2, 2)

    async def test__blacklists_track_only(
        self,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        blacklist_choices = [
            BlacklistChoiceInput(
                track_name="Bad Track",
                artist_name="Bad Artist",
                blacklist_track=True,
                blacklist_artist=False,
            )
        ]

        await discovery_playlist_rate(
            user=user,
            ratings=[],
            blacklist_choices=blacklist_choices,
            discovery_playlist_repository=mock_discovery_playlist_repository,
            blacklist_repository=mock_blacklist_repository,
        )

        mock_blacklist_repository.add_track.assert_awaited_once_with(user.id, "Bad Track", "Bad Artist")
        mock_blacklist_repository.add_artist.assert_not_awaited()

    async def test__blacklists_artist_only(
        self,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        blacklist_choices = [
            BlacklistChoiceInput(
                track_name="Bad Track",
                artist_name="Bad Artist",
                blacklist_track=False,
                blacklist_artist=True,
            )
        ]

        await discovery_playlist_rate(
            user=user,
            ratings=[],
            blacklist_choices=blacklist_choices,
            discovery_playlist_repository=mock_discovery_playlist_repository,
            blacklist_repository=mock_blacklist_repository,
        )

        mock_blacklist_repository.add_track.assert_not_awaited()
        mock_blacklist_repository.add_artist.assert_awaited_once_with(user.id, "Bad Artist")

    async def test__blacklists_both_track_and_artist(
        self,
        mock_discovery_playlist_repository: mock.AsyncMock,
        mock_blacklist_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        blacklist_choices = [
            BlacklistChoiceInput(
                track_name="Awful Song",
                artist_name="Awful Artist",
                blacklist_track=True,
                blacklist_artist=True,
            )
        ]

        await discovery_playlist_rate(
            user=user,
            ratings=[],
            blacklist_choices=blacklist_choices,
            discovery_playlist_repository=mock_discovery_playlist_repository,
            blacklist_repository=mock_blacklist_repository,
        )

        mock_blacklist_repository.add_track.assert_awaited_once_with(user.id, "Awful Song", "Awful Artist")
        mock_blacklist_repository.add_artist.assert_awaited_once_with(user.id, "Awful Artist")
