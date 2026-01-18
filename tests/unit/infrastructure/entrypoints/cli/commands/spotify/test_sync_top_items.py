from collections.abc import Iterable
from typing import Any
from typing import Final
from typing import get_args
from unittest import mock

import pytest
import typer
from typer.testing import CliRunner

from spotifagent.application.services.spotify import TimeRange
from spotifagent.application.use_cases.spotify_sync_top_items import SyncReport
from spotifagent.domain.entities.users import User
from spotifagent.infrastructure.entrypoints.cli.commands.spotify import sync_top_items_logic
from spotifagent.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.users import UserFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TIME_RANGE_OPTIONS_OUTPUT: Final[str] = ", ".join([f"'{tr}'" for tr in get_args(TimeRange)])


class TestSpotifySyncTopItemCommand:
    @pytest.fixture(autouse=True)
    def mock_sync_top_items_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "spotifagent.infrastructure.entrypoints.cli.commands.spotify.sync_top_items_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "spotify",
                "sync-top-items",
                "--email", "test@example.com",
                "--purge-top-artists",
                "--purge-top-tracks",
                "--no-sync-top-artists",
                "--no-sync-top-tracks",
                "--page-limit", "20",
                "--time-range", "medium_term",
                "--batch-size", "100",
            ],
        )
        # fmt: on
        assert result.exit_code == 0

    @pytest.mark.parametrize(
        ("email", "expected_msg"),
        [
            pytest.param(
                "testtest.com",
                "An email address must have an @-sign",
                id="missing_@",
            ),
            pytest.param(
                "test@test",
                "The part after the @-sign is not valid. It should have a period",
                id="missing_dot",
            ),
        ],
    )
    def test__email__invalid(
        self,
        runner: CliRunner,
        email: str,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["spotify", "sync-top-items", "--email", email])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output

    @pytest.mark.parametrize(
        ("page_limit", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--page-limit': 0 is not in the range", id="zero"),
            pytest.param(-15, "Invalid value for '--page-limit': -15 is not in the range", id="min_exceed"),
            pytest.param(55, "Invalid value for '--page-limit': 55 is not in the range", id="max_exceed"),
            pytest.param("foo", "Invalid value for '--page-limit': 'foo' is not a valid integer", id="string"),
        ],
    )
    def test__page_limit__invalid(
        self,
        runner: CliRunner,
        page_limit: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["spotify", "sync-top-items", "--email", "test@example.com", "--page-limit", page_limit],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output

    @pytest.mark.parametrize(
        ("time_range", "expected_msg"),
        [
            pytest.param(
                "foo",
                f"Invalid value for '--time-range': 'foo' is not one of {TIME_RANGE_OPTIONS_OUTPUT}",
                id="invalid-choice",
            ),
        ],
    )
    def test__time_range__invalid(
        self,
        runner: CliRunner,
        time_range: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["spotify", "sync-top-items", "--email", "test@example.com", "--time-range", time_range],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output

    @pytest.mark.parametrize(
        ("batch_size", "expected_msg"),
        [
            pytest.param(0, "Invalid value for '--batch-size': 0 is not in the range", id="zero"),
            pytest.param(-15, "Invalid value for '--batch-size': -15 is not in the range", id="min_exceed"),
            pytest.param(1000, "Invalid value for '--batch-size': 1000 is not in the range", id="max_exceed"),
            pytest.param("foo", "Invalid value for '--batch-size': 'foo' is not a valid integer", id="string"),
        ],
    )
    def test__batch_size__invalid(
        self,
        runner: CliRunner,
        batch_size: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["spotify", "sync-top-items", "--email", "test@example.com", "--batch-size", batch_size],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert expected_msg in output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_top_artist_repository",
    "mock_top_track_repository",
    "mock_spotify_client",
)
class TestSpotifySyncTopItemsLogic:
    TARGET_PATH: Final[str] = "spotifagent.infrastructure.entrypoints.cli.commands.spotify.sync_top_items"

    @pytest.fixture(autouse=True)
    def mock_spotify_sync_top_items(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{self.TARGET_PATH}.spotify_sync_top_items", new_callable=mock.AsyncMock) as patched:
            yield patched

    @pytest.fixture(autouse=True)
    def mock_typer_launch(self) -> Iterable[mock.Mock]:
        with mock.patch(f"{self.TARGET_PATH}.typer.launch") as patched:
            yield patched

    @pytest.fixture
    def user(self) -> User:
        return UserFactory.build(with_spotify_account=True)

    async def test__do_nothing(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_spotify_sync_top_items: mock.AsyncMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_spotify_sync_top_items.return_value = SyncReport()

        with pytest.raises(typer.Abort):
            await sync_top_items_logic(
                user.email,
                purge_top_artists=False,
                purge_top_tracks=False,
                sync_top_artists=False,
                sync_top_tracks=False,
            )

        captured = capsys.readouterr()
        assert "At least one flag must be provided." in captured.err

    async def test__user__not_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_spotify_sync_top_items: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = None

        email = "test@example.com"
        with pytest.raises(typer.BadParameter, match=f"User not found with email: {email}"):
            await sync_top_items_logic(email, sync_top_artists=True)

    async def test__output__errors(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_spotify_sync_top_items: mock.AsyncMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_spotify_sync_top_items.return_value = SyncReport(errors=["An error occurred: Boom"])

        with pytest.raises(typer.Abort):
            await sync_top_items_logic(user.email, sync_top_artists=True)

        captured = capsys.readouterr()
        assert "An error occurred: Boom" in captured.err

    async def test__output__purge_top_artists(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_spotify_sync_top_items: mock.AsyncMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_spotify_sync_top_items.return_value = SyncReport(purge_top_artist=330)

        await sync_top_items_logic(
            user.email,
            purge_top_artists=True,
            purge_top_tracks=False,
            sync_top_artists=False,
            sync_top_tracks=False,
        )

        captured = capsys.readouterr()
        assert "Synchronization successful!" in captured.out
        assert "- 330 top artists purged" in captured.out

    async def test__output__purge_top_tracks(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_spotify_sync_top_items: mock.AsyncMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_spotify_sync_top_items.return_value = SyncReport(purge_top_track=550)

        await sync_top_items_logic(
            user.email,
            purge_top_artists=False,
            purge_top_tracks=True,
            sync_top_artists=False,
            sync_top_tracks=False,
        )

        captured = capsys.readouterr()
        assert "Synchronization successful!" in captured.out
        assert "- 550 top tracks purged" in captured.out

    async def test__output__sync_top_artists(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_spotify_sync_top_items: mock.AsyncMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_spotify_sync_top_items.return_value = SyncReport(
            top_artist_created=100,
            top_artist_updated=250,
        )

        await sync_top_items_logic(
            user.email,
            purge_top_artists=False,
            purge_top_tracks=False,
            sync_top_artists=True,
            sync_top_tracks=False,
        )

        captured = capsys.readouterr()
        assert "Synchronization successful!" in captured.out
        assert "- 100 top artists created" in captured.out
        assert "- 250 top artists updated" in captured.out

    async def test__output__sync_top_tracks(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_spotify_sync_top_items: mock.AsyncMock,
        capsys: pytest.CaptureFixture,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_spotify_sync_top_items.return_value = SyncReport(
            top_track_created=50,
            top_track_updated=150,
        )

        await sync_top_items_logic(
            user.email,
            purge_top_artists=False,
            purge_top_tracks=False,
            sync_top_artists=False,
            sync_top_tracks=True,
        )

        captured = capsys.readouterr()
        assert "Synchronization successful!" in captured.out
        assert "- 50 top tracks created" in captured.out
        assert "- 150 top tracks updated" in captured.out
