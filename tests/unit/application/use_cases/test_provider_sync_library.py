import itertools
import logging
from typing import Any
from unittest import mock

from httpx import HTTPError

from pydantic import BaseModel
from pydantic import ValidationError
from pydantic import model_validator

from sqlalchemy.exc import SQLAlchemyError

import pytest

from museflow.application.use_cases.provider_sync_library import ProviderSyncLibraryUseCase
from museflow.application.use_cases.provider_sync_library import SyncConfig
from museflow.application.use_cases.provider_sync_library import SyncReport
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Track
from museflow.domain.entities.user import User
from museflow.domain.ports.providers.library import ProviderLibraryPort

from tests.unit.factories.entities.music import ArtistFactory
from tests.unit.factories.entities.music import TrackFactory


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


class TestSyncConfig:
    @pytest.mark.parametrize(
        ("attributes", "expected_bool"),
        [
            ({}, False),
            ({"purge_all": True}, True),
            ({"purge_artist_top": True}, True),
            ({"purge_track_top": True}, True),
            ({"purge_track_saved": True}, True),
            ({"purge_track_playlist": True}, True),
        ],
    )
    def test_has_purge(self, attributes: dict[str, Any], expected_bool: bool) -> None:
        config = SyncConfig(**attributes)
        assert config.has_purge() is expected_bool

    @pytest.mark.parametrize(
        ("attributes", "expected_bool"),
        [
            ({}, False),
            ({"sync_all": True}, True),
            ({"sync_artist_top": True}, True),
            ({"sync_track_top": True}, True),
            ({"sync_track_saved": True}, True),
            ({"sync_track_playlist": True}, True),
        ],
    )
    def test_has_sync(self, attributes: dict[str, Any], expected_bool: bool) -> None:
        config = SyncConfig(**attributes)
        assert config.has_sync() is expected_bool


class TestSyncMusic:
    @pytest.fixture
    def artists(self) -> list[Artist]:
        return ArtistFactory.batch(size=10)

    @pytest.fixture
    def tracks(self) -> list[Track]:
        return TrackFactory.batch(size=10)

    @pytest.fixture
    def mock_provider_library(self, artists: list[Artist], tracks: list[Track]) -> mock.Mock:
        return mock.Mock(
            spec=ProviderLibraryPort,
            get_top_artists=mock.AsyncMock(return_value=artists),
            get_top_tracks=mock.AsyncMock(return_value=tracks),
            get_saved_tracks=mock.AsyncMock(return_value=tracks),
        )

    @pytest.fixture
    def use_case(
        self,
        mock_provider_library: mock.Mock,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> ProviderSyncLibraryUseCase:
        return ProviderSyncLibraryUseCase(
            provider_library=mock_provider_library,
            artist_repository=mock_artist_repository,
            track_repository=mock_track_repository,
        )

    async def test__do_nothing(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        use_case: ProviderSyncLibraryUseCase,
    ) -> None:
        report = await use_case.execute(
            user=user,
            config=SyncConfig(),
        )
        assert report == SyncReport()

    @pytest.mark.parametrize(("purge_all", "purge_artist_top"), [(True, True), (True, False), (False, True)])
    async def test__purge__artist__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        purge_all: bool,
        purge_artist_top: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_artist_repository.purge.side_effect = SQLAlchemyError("Boom")
        mock_track_repository.purge.return_value = 0

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    purge_all=purge_all,
                    purge_artist_top=purge_artist_top,
                ),
            )

        assert report == SyncReport(errors=[mock.ANY])
        assert "An error occurred while purging your artists." in report.errors
        assert f"An error occurred while purging artists for user {user.email}" in caplog.text

    @pytest.mark.parametrize(
        ("purge_all", "purge_track_top", "purge_track_saved", "purge_track_playlist"),
        [c for c in itertools.product([True, False], repeat=4) if any(c)],
    )
    async def test__purge__track__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        purge_all: bool,
        purge_track_top: bool,
        purge_track_saved: bool,
        purge_track_playlist: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_artist_repository.purge.return_value = 0
        mock_track_repository.purge.side_effect = SQLAlchemyError("Boom")

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    purge_all=purge_all,
                    purge_track_top=purge_track_top,
                    purge_track_saved=purge_track_saved,
                    purge_track_playlist=purge_track_playlist,
                ),
            )

        assert report == SyncReport(errors=[mock.ANY])
        assert "An error occurred while purging your tracks." in report.errors
        assert f"An error occurred while purging tracks for user {user.email}" in caplog.text

    @pytest.mark.parametrize(
        ("sync_all", "sync_artist_top", "exception_raised"),
        [
            (True, False, HTTPError("Boom")),
            (False, True, validation_error()),
        ],
    )
    async def test__artist_top__fetch__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        sync_all: bool,
        sync_artist_top: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_provider_library: mock.Mock,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_provider_library.get_top_artists.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    sync_all=sync_all,
                    sync_artist_top=sync_artist_top,
                ),
            )

        assert report == SyncReport(errors=mock.ANY)
        assert "An error occurred while fetching top artists." in report.errors
        assert f"An error occurred while fetching top artists for user {user.email}" in caplog.text

    @pytest.mark.parametrize(
        ("sync_all", "sync_artist_top", "exception_raised"),
        [
            (True, False, SQLAlchemyError("Boom")),
            (False, True, validation_error()),
        ],
    )
    async def test__artist_top__bulk_upsert__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        sync_all: bool,
        sync_artist_top: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_provider_library: mock.Mock,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_artist_repository.bulk_upsert.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    sync_all=sync_all,
                    sync_artist_top=sync_artist_top,
                ),
            )

        assert report == SyncReport(errors=mock.ANY)
        assert "An error occurred while saving top artists." in report.errors
        assert f"An error occurred while upserting top artists for user {user.email}" in caplog.text

    @pytest.mark.parametrize(
        ("sync_all", "sync_track_top", "exception_raised"),
        [
            (True, False, HTTPError("Boom")),
            (False, True, validation_error()),
        ],
    )
    async def test__track_top__fetch__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        sync_all: bool,
        sync_track_top: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_provider_library: mock.Mock,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_provider_library.get_top_tracks.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    sync_all=sync_all,
                    sync_track_top=sync_track_top,
                ),
            )

        assert report == SyncReport(errors=mock.ANY)
        assert "An error occurred while fetching top tracks." in report.errors
        assert f"An error occurred while fetching top tracks for user {user.email}" in caplog.text

    @pytest.mark.parametrize(
        ("sync_all", "sync_track_top", "exception_raised"),
        [
            (True, False, SQLAlchemyError("Boom")),
            (False, True, validation_error()),
        ],
    )
    async def test__track_top__bulk_upsert__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        sync_all: bool,
        sync_track_top: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_provider_library: mock.Mock,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_track_repository.bulk_upsert.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    sync_all=sync_all,
                    sync_track_top=sync_track_top,
                ),
            )

        assert report == SyncReport(errors=mock.ANY)
        assert "An error occurred while saving top tracks." in report.errors
        assert f"An error occurred while upserting top tracks for user {user.email}" in caplog.text

    @pytest.mark.parametrize(
        ("sync_all", "sync_track_saved", "exception_raised"),
        [
            (True, False, HTTPError("Boom")),
            (False, True, validation_error()),
        ],
    )
    async def test__track_saved__fetch__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        sync_all: bool,
        sync_track_saved: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_provider_library: mock.Mock,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_provider_library.get_saved_tracks.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    sync_all=sync_all,
                    sync_track_saved=sync_track_saved,
                ),
            )

        assert report == SyncReport(errors=mock.ANY)
        assert "An error occurred while fetching saved tracks." in report.errors
        assert f"An error occurred while fetching saved tracks for user {user.email}" in caplog.text

    @pytest.mark.parametrize(
        ("sync_all", "sync_track_saved", "exception_raised"),
        [
            (True, False, SQLAlchemyError("Boom")),
            (False, True, validation_error()),
        ],
    )
    async def test__track_saved__bulk_upsert__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        sync_all: bool,
        sync_track_saved: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_provider_library: mock.Mock,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_track_repository.bulk_upsert.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    sync_all=sync_all,
                    sync_track_saved=sync_track_saved,
                ),
            )

        assert report == SyncReport(errors=mock.ANY)
        assert "An error occurred while saving saved tracks." in report.errors
        assert f"An error occurred while upserting saved tracks for user {user.email}" in caplog.text

    @pytest.mark.parametrize(
        ("sync_all", "sync_track_playlist", "exception_raised"),
        [
            (True, False, HTTPError("Boom")),
            (False, True, validation_error()),
        ],
    )
    async def test__track_playlist__fetch__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        sync_all: bool,
        sync_track_playlist: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_provider_library: mock.Mock,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_provider_library.get_playlist_tracks.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    sync_all=sync_all,
                    sync_track_playlist=sync_track_playlist,
                ),
            )

        assert report == SyncReport(errors=mock.ANY)
        assert "An error occurred while fetching playlist tracks." in report.errors
        assert f"An error occurred while fetching playlist tracks for user {user.email}" in caplog.text

    @pytest.mark.parametrize(
        ("sync_all", "sync_track_playlist", "exception_raised"),
        [
            (True, False, SQLAlchemyError("Boom")),
            (False, True, validation_error()),
        ],
    )
    async def test__track_playlist__bulk_upsert__exception(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        sync_all: bool,
        sync_track_playlist: bool,
        use_case: ProviderSyncLibraryUseCase,
        mock_provider_library: mock.Mock,
        mock_artist_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        exception_raised: Exception,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_track_repository.bulk_upsert.side_effect = exception_raised

        with caplog.at_level(logging.ERROR):
            report = await use_case.execute(
                user=user,
                config=SyncConfig(
                    sync_all=sync_all,
                    sync_track_playlist=sync_track_playlist,
                ),
            )

        assert report == SyncReport(errors=mock.ANY)
        assert "An error occurred while saving playlist tracks." in report.errors
        assert f"An error occurred while upserting playlist tracks for user {user.email}" in caplog.text
