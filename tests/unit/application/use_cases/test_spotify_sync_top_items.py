import logging
from unittest import mock

from httpx import HTTPError

from pydantic import BaseModel
from pydantic import ValidationError
from pydantic import model_validator

from sqlalchemy.exc import SQLAlchemyError

import pytest

from spotifagent.application.services.spotify import SpotifySessionFactory
from spotifagent.application.services.spotify import SpotifyUserSession
from spotifagent.application.use_cases.spotify_sync_top_items import SyncReport
from spotifagent.application.use_cases.spotify_sync_top_items import spotify_sync_top_items
from spotifagent.domain.entities.music import TopArtist
from spotifagent.domain.entities.music import TopTrack
from spotifagent.domain.entities.users import User
from spotifagent.domain.exceptions import SpotifyAccountNotFoundError

from tests.unit.factories.music import TopArtistFactory
from tests.unit.factories.music import TopTrackFactory
from tests.unit.factories.users import UserFactory


def validation_error() -> ValidationError:
    """
    Mimic a dummy Pydantic ValidationError with a KISS approach.

    Indeed, we tried to instance it manually but the signature is not obvious
    at all and may change in the future (whereas this dummy code shouldn't!).
    """

    class DummyModel(BaseModel):
        dummy_field: int

        @model_validator(mode="after")
        def blow_up(self):
            raise ValueError("Boom")

    with pytest.raises(ValidationError) as exc_info:
        DummyModel(dummy_field=50)

    return exc_info.value


class TestSpotifySyncTopItems:
    @pytest.fixture
    def user(self) -> User:
        return UserFactory.build(with_spotify_account=True)

    @pytest.fixture
    def top_artists(self) -> list[TopArtist]:
        return TopArtistFactory.batch(size=10)

    @pytest.fixture
    def top_tracks(self) -> list[TopTrack]:
        return TopTrackFactory.batch(size=10)

    @pytest.fixture
    def mock_spotify_session(self, user: User, top_artists: list[TopArtist], top_tracks: list[TopTrack]) -> mock.Mock:
        return mock.Mock(
            spec=SpotifyUserSession,
            user=user,
            get_top_artists=mock.AsyncMock(return_value=top_artists),
            get_top_tracks=mock.AsyncMock(return_value=top_tracks),
        )

    @pytest.fixture
    def mock_spotify_session_factory(self, mock_spotify_session: mock.Mock) -> mock.Mock:
        return mock.Mock(
            spec=SpotifySessionFactory,
            create=mock.Mock(return_value=mock_spotify_session),
        )

    async def test__do_nothing(
        self,
        user: User,
        mock_spotify_session_factory: mock.Mock,
        mock_top_artist_repository: mock.Mock,
        mock_top_track_repository: mock.Mock,
    ) -> None:
        report = await spotify_sync_top_items(
            user=user,
            spotify_session_factory=mock_spotify_session_factory,
            top_artist_repository=mock_top_artist_repository,
            top_track_repository=mock_top_track_repository,
        )
        assert report == SyncReport()

    async def test__purge__top_artist__exception(
        self,
        user: User,
        mock_spotify_session_factory: mock.Mock,
        mock_top_artist_repository: mock.Mock,
        mock_top_track_repository: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_top_artist_repository.purge.side_effect = SQLAlchemyError("Boom")

        with caplog.at_level(logging.ERROR):
            report = await spotify_sync_top_items(
                user=user,
                spotify_session_factory=mock_spotify_session_factory,
                top_artist_repository=mock_top_artist_repository,
                top_track_repository=mock_top_track_repository,
                purge_top_artists=True,
            )

        assert report == SyncReport(errors=["An error occurred while purging your top artists."])
        assert f"An error occurred while purging top artists for user {user.email}" in caplog.text

    async def test__purge__top_track__exception(
        self,
        user: User,
        mock_spotify_session_factory: mock.Mock,
        mock_top_artist_repository: mock.Mock,
        mock_top_track_repository: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_top_track_repository.purge.side_effect = SQLAlchemyError("Boom")

        with caplog.at_level(logging.ERROR):
            report = await spotify_sync_top_items(
                user=user,
                spotify_session_factory=mock_spotify_session_factory,
                top_artist_repository=mock_top_artist_repository,
                top_track_repository=mock_top_track_repository,
                purge_top_tracks=True,
            )

        assert report == SyncReport(errors=["An error occurred while purging your top tracks."])
        assert f"An error occurred while purging top tracks for user {user.email}" in caplog.text

    async def test__user__spotify_account_not_found(
        self,
        user: User,
        mock_spotify_session_factory: mock.Mock,
        mock_top_artist_repository: mock.Mock,
        mock_top_track_repository: mock.Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_spotify_session_factory.create.side_effect = SpotifyAccountNotFoundError("Boom")

        with caplog.at_level(logging.DEBUG):
            report = await spotify_sync_top_items(
                user=user,
                spotify_session_factory=mock_spotify_session_factory,
                top_artist_repository=mock_top_artist_repository,
                top_track_repository=mock_top_track_repository,
            )

        assert report == SyncReport(errors=["You must connect your Spotify account first."])
        assert f"Spotify account not found for user {user.email}" in caplog.text

    @pytest.mark.parametrize("exception_raised", [HTTPError("Boom"), validation_error()])
    async def test__top_artist__fetch__exception(
        self,
        user: User,
        mock_spotify_session_factory: mock.Mock,
        mock_spotify_session: mock.Mock,
        mock_top_artist_repository: mock.Mock,
        mock_top_track_repository: mock.Mock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_spotify_session.get_top_artists.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await spotify_sync_top_items(
                user=user,
                spotify_session_factory=mock_spotify_session_factory,
                top_artist_repository=mock_top_artist_repository,
                top_track_repository=mock_top_track_repository,
                sync_top_artists=True,
            )

        assert report == SyncReport(errors=["An error occurred while fetching Spotify top artists."])
        assert f"An error occurred while fetching top artists for user {user.email}" in caplog.text

    @pytest.mark.parametrize("exception_raised", [SQLAlchemyError("Boom"), validation_error()])
    async def test__top_artist__bulk_upsert__exception(
        self,
        user: User,
        mock_spotify_session_factory: mock.Mock,
        mock_spotify_session: mock.Mock,
        mock_top_artist_repository: mock.Mock,
        mock_top_track_repository: mock.Mock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_top_artist_repository.bulk_upsert.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await spotify_sync_top_items(
                user=user,
                spotify_session_factory=mock_spotify_session_factory,
                top_artist_repository=mock_top_artist_repository,
                top_track_repository=mock_top_track_repository,
                sync_top_artists=True,
            )

        assert report == SyncReport(errors=["An error occurred while saving Spotify top artists."])
        assert f"An error occurred while upserting top artists for user {user.email}" in caplog.text

    @pytest.mark.parametrize("exception_raised", [HTTPError("Boom"), validation_error()])
    async def test__top_track__fetch__exception(
        self,
        user: User,
        mock_spotify_session_factory: mock.Mock,
        mock_spotify_session: mock.Mock,
        mock_top_artist_repository: mock.Mock,
        mock_top_track_repository: mock.Mock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_spotify_session.get_top_tracks.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await spotify_sync_top_items(
                user=user,
                spotify_session_factory=mock_spotify_session_factory,
                top_artist_repository=mock_top_artist_repository,
                top_track_repository=mock_top_track_repository,
                sync_top_tracks=True,
            )

        assert report == SyncReport(errors=["An error occurred while fetching Spotify top tracks."])
        assert f"An error occurred while fetching top tracks for user {user.email}" in caplog.text

    @pytest.mark.parametrize("exception_raised", [SQLAlchemyError("Boom"), validation_error()])
    async def test__top_track__bulk_upsert__exception(
        self,
        user: User,
        mock_spotify_session_factory: mock.Mock,
        mock_spotify_session: mock.Mock,
        mock_top_artist_repository: mock.Mock,
        mock_top_track_repository: mock.Mock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_top_track_repository.bulk_upsert.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await spotify_sync_top_items(
                user=user,
                spotify_session_factory=mock_spotify_session_factory,
                top_artist_repository=mock_top_artist_repository,
                top_track_repository=mock_top_track_repository,
                sync_top_tracks=True,
            )

        assert report == SyncReport(errors=["An error occurred while saving Spotify top tracks."])
        assert f"An error occurred while upserting top tracks for user {user.email}" in caplog.text
