from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
import typer
from typer.testing import CliRunner

from museflow.domain.entities.track import Track
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.tracks.delete import TracksDeleteResult
from museflow.infrastructure.entrypoints.cli.commands.tracks.delete import delete_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.track import TrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.tracks.delete"


class TestDeleteParserCommand:
    @pytest.fixture(autouse=True)
    def mock_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.delete_logic", new_callable=mock.AsyncMock) as patched:
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


class TestDeleteCommand:
    @pytest.fixture(autouse=True)
    def mock_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.delete_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = TracksDeleteResult(deleted_count=3)
            yield patched

    def test__nominal(self, runner: CliRunner, mock_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--yes"])
        assert result.exit_code == 0
        assert "Deleted 3" in result.output
        mock_delete_logic.assert_called_once()

    def test__no_tracks__early_exit(self, runner: CliRunner, mock_delete_logic: mock.AsyncMock) -> None:
        mock_delete_logic.return_value = TracksDeleteResult(no_tracks=True)
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--yes"])
        assert result.exit_code == 0
        assert "No tracks found" in result.output

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_delete_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--yes"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exception(
        self,
        runner: CliRunner,
        mock_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_delete_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["tracks", "delete", "--email", "test@example.com", "--artist", "X", "--yes"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_track_repository")
class TestDeleteLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await delete_logic(email="unknown@example.com", artist="X", name=None, source=None, provider=None)  # type: ignore[arg-type]

    async def test__no_tracks_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        result = await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
            artist="X",
            name=None,
            source=None,
            provider=None,
            yes=True,
        )

        assert result == TracksDeleteResult(no_tracks=True)
        mock_track_repository.delete.assert_not_awaited()

    async def test__name_filter_applied_in_python(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        matching = TrackFactory.build(name="Creep")
        non_matching = TrackFactory.build(name="Karma Police")
        mock_track_repository.get_list.return_value = [matching, non_matching]
        mock_track_repository.delete.return_value = 1

        result = await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
            artist=None,
            name="creep",
            source=None,
            provider=None,
            yes=True,
        )

        assert result == TracksDeleteResult(deleted_count=1)

    async def test__artist_only__shows_track_names(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        tracks: list[Track] = TrackFactory.batch(size=3)
        mock_track_repository.get_list.return_value = tracks
        mock_track_repository.delete.return_value = 3

        await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
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

        await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
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
        mock_track_repository.delete.return_value = 3

        await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
            artist=None,
            name=None,
            source=None,
            provider=None,
            purge=True,
            yes=True,
        )

        output = capsys.readouterr().out
        for track in tracks:
            assert track.name not in output

    async def test__confirmation_accepted(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=2)
        mock_track_repository.delete.return_value = 2
        mock_typer_confirm.return_value = True

        result = await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
            artist="X",
            name=None,
            source=None,
            provider=None,
        )

        assert result == TracksDeleteResult(deleted_count=2)
        mock_typer_confirm.assert_called_once()

    async def test__confirmation_declined__aborts(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
        mock_typer_confirm: mock.Mock,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=2)
        mock_typer_confirm.side_effect = typer.Abort()

        with pytest.raises(typer.Abort):
            await delete_logic(
                email="test@example.com",  # type: ignore[arg-type]
                artist="X",
                name=None,
                source=None,
                provider=None,
            )

        mock_track_repository.delete.assert_not_awaited()

    async def test__source_filter_passed_to_repo(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = [TrackFactory.build(name="Creep")]
        mock_track_repository.delete.return_value = 1

        await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
            artist="Radiohead",
            name="Creep",
            source=TrackSource.HISTORY,
            provider=None,
            yes=True,
        )

        mock_track_repository.get_list.assert_called_once_with(
            user_id=mock_user_repository.get_by_email.return_value.id,
            artist_name="Radiohead",
            source=TrackSource.HISTORY,
            provider=None,
        )
        mock_track_repository.delete.assert_called_once_with(
            user_id=mock_user_repository.get_by_email.return_value.id,
            artist_name="Radiohead",
            track_name="Creep",
            source=TrackSource.HISTORY,
            provider=None,
        )

    async def test__provider_filter_passed_to_repo(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = TrackFactory.batch(size=1)
        mock_track_repository.delete.return_value = 1

        await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
            artist=None,
            name=None,
            source=None,
            provider=MusicProvider.SPOTIFY,
            purge=True,
            yes=True,
        )

        mock_track_repository.get_list.assert_called_once_with(
            user_id=mock_user_repository.get_by_email.return_value.id,
            artist_name=None,
            source=None,
            provider=MusicProvider.SPOTIFY,
        )
        mock_track_repository.delete.assert_called_once_with(
            user_id=mock_user_repository.get_by_email.return_value.id,
            artist_name=None,
            track_name=None,
            source=None,
            provider=MusicProvider.SPOTIFY,
        )
