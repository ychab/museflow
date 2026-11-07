from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
import typer
from typer.testing import CliRunner

from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.tracks.delete import TracksDeleteResult
from museflow.infrastructure.entrypoints.cli.commands.tracks.delete import tracks_delete_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.tracks.delete"


class TestTracksDeleteParserCommand:
    @pytest.fixture(autouse=True)
    def mock_tracks_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.tracks_delete_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = TracksDeleteResult()
            yield patched

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["tracks", "delete", "--email", "notanemail", "--artist", "X"])
        assert result.exit_code != 0
        assert "An email address must have an @-sign" in clean_typer_text(result.output)

    def test__no_filters__fails(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "--artist or --name" in clean_typer_text(result.output)

    @pytest.mark.parametrize("option", ["--artist", "--name"])
    def test__purge__with_artist_or_name__fails(
        self,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
        option: str,
    ) -> None:
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com", "--purge", option, "X"])
        assert result.exit_code != 0
        assert "can't be combined with --artist or --name" in clean_typer_text(result.output)

    def test__source__invalid(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--source", "bad"]
        )
        assert result.exit_code != 0

    def test__provider__invalid(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--provider", "bad"]
        )
        assert result.exit_code != 0


class TestTracksDeleteCommand:
    @pytest.fixture(autouse=True)
    def mock_tracks_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.tracks_delete_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = TracksDeleteResult(deleted_count=3)
            yield patched

    def test__nominal(self, runner: CliRunner, mock_tracks_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--yes"])
        assert result.exit_code == 0
        assert "Deleted 3 track(s) of test@example.com." in result.output
        mock_tracks_delete_logic.assert_called_once()

    def test__no_tracks__early_exit(self, runner: CliRunner, mock_tracks_delete_logic: mock.AsyncMock) -> None:
        mock_tracks_delete_logic.return_value = TracksDeleteResult(no_tracks=True)
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--yes"])
        assert result.exit_code == 0
        assert "No tracks found" in result.output

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_tracks_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_tracks_delete_logic.side_effect = UserNotFoundError()
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--yes"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exception(
        self,
        runner: CliRunner,
        mock_tracks_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_tracks_delete_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--yes"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_unit_of_work", "mock_user_repository", "mock_track_repository")
class TestTracksDeleteLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFoundError):
            await tracks_delete_logic(email="unknown@example.com", artist="X", name=None, source=None, provider=None)

    async def test__no_tracks_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        result = await tracks_delete_logic(
            email="test@example.com",
            artist="X",
            name=None,
            source=None,
            provider=None,
            yes=True,
        )

        assert result == TracksDeleteResult(no_tracks=True)
        mock_track_repository.delete.assert_not_awaited()

    async def test__artist_only__shows_track_names(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        tracks: list[Track] = TrackFactory.batch(size=3)
        mock_track_repository.get_list.return_value = tracks
        mock_track_repository.delete.return_value = 3

        await tracks_delete_logic(
            email="test@example.com",
            artist="Radiohead",
            name=None,
            source=None,
            provider=None,
            yes=True,
        )

        output = capsys.readouterr().out
        for track in tracks:
            assert track.name in output

    async def test__name_filter__no_track_list_shown(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        tracks: list[Track] = TrackFactory.batch(size=3)
        mock_track_repository.get_list.return_value = tracks
        mock_track_repository.delete.return_value = 3

        await tracks_delete_logic(
            email="test@example.com",
            artist="Radiohead",
            name="Creep",
            source=None,
            provider=None,
            yes=True,
        )

        output = capsys.readouterr().out
        for track in tracks:
            assert track.name not in output

    async def test__purge__no_track_list_shown(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        tracks: list[Track] = TrackFactory.batch(size=3)
        mock_track_repository.get_list.return_value = tracks
        mock_track_repository.purge.return_value = 3

        result = await tracks_delete_logic(
            email="test@example.com",
            artist=None,
            name=None,
            source=None,
            provider=None,
            purge=True,
            yes=True,
        )

        assert result == TracksDeleteResult(deleted_count=3)
        mock_track_repository.delete.assert_not_awaited()
        output = capsys.readouterr().out
        for track in tracks:
            assert track.name not in output

    async def test__purge__with_provider__unlinks_the_whole_library(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user = mock_user_repository.get_by_email.return_value
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=2)
        mock_track_repository.unlink_provider.return_value = []
        mock_track_repository.delete.return_value = 0

        await tracks_delete_logic(
            email="test@example.com",
            artist=None,
            name=None,
            source=None,
            provider=MusicProvider.SPOTIFY,
            purge=True,
            yes=True,
        )

        mock_track_repository.unlink_provider.assert_awaited_once_with(user_id=user.id, provider=MusicProvider.SPOTIFY)
        mock_track_repository.purge.assert_not_awaited()

    async def test__purge__with_source__deletes_the_ids(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        user = mock_user_repository.get_by_email.return_value
        tracks = TrackFactory.batch(size=2)
        mock_track_repository.get_list.return_value = tracks
        mock_track_repository.delete.return_value = 2

        result = await tracks_delete_logic(
            email="test@example.com",
            artist=None,
            name=None,
            source=TrackSource.HISTORY,
            provider=None,
            purge=True,
            yes=True,
        )

        assert result == TracksDeleteResult(deleted_count=2)
        mock_track_repository.purge.assert_not_awaited()
        mock_track_repository.delete.assert_awaited_once_with(
            user_id=user.id,
            track_ids=[track.id for track in tracks],
        )

    async def test__confirmation_accepted(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        user = mock_user_repository.get_by_email.return_value
        tracks = TrackFactory.batch(size=2)
        mock_track_repository.get_list.return_value = tracks
        mock_track_repository.delete.return_value = 2
        mock_typer_confirm.return_value = True

        result = await tracks_delete_logic(
            email="test@example.com",
            artist="X",
            name=None,
            source=None,
            provider=None,
        )

        assert result == TracksDeleteResult(deleted_count=2)
        mock_typer_confirm.assert_called_once_with(
            "About to delete 2 track(s) of test@example.com. Continue?", abort=True
        )
        mock_track_repository.delete.assert_awaited_once_with(
            user_id=user.id,
            track_ids=[track.id for track in tracks],
        )

    async def test__confirmation_declined__aborts(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=2)
        mock_typer_confirm.side_effect = typer.Abort()

        with pytest.raises(typer.Abort):
            await tracks_delete_logic(
                email="test@example.com",
                artist="X",
                name=None,
                source=None,
                provider=None,
            )

        mock_track_repository.delete.assert_not_awaited()
