import uuid
from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import MusicProvider
from museflow.domain.types import PlaylistType
from museflow.infrastructure.entrypoints.cli.commands.playlist.delete import delete_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.playlist.delete"


class TestDeleteParserCommand:
    @pytest.fixture(autouse=True)
    def mock_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.delete_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = 1
            yield patched

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["playlist", "delete", str(uuid.uuid4()), "--email", "notanemail"])
        assert result.exit_code != 0
        assert "An email address must have an @-sign" in clean_typer_text(result.output)

    def test__playlist_id__invalid(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["playlist", "delete", "not-a-uuid", "--email", "test@example.com"])
        assert result.exit_code != 0

    def test__type__invalid(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app, ["playlist", "delete", "--purge", "--email", "test@example.com", "--type", "bad", "--yes"]
        )
        assert result.exit_code != 0

    def test__provider__invalid(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app, ["playlist", "delete", "--purge", "--email", "test@example.com", "--provider", "bad", "--yes"]
        )
        assert result.exit_code != 0

    def test__no_playlist_id_and_no_purge__fails(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["playlist", "delete", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "Provide a playlist ID, or use --purge" in clean_typer_text(result.output)

    def test__playlist_id_and_purge__fails(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app, ["playlist", "delete", str(uuid.uuid4()), "--purge", "--email", "test@example.com", "--yes"]
        )
        assert result.exit_code != 0
        assert "Provide either a playlist ID or --purge, not both" in clean_typer_text(result.output)

    def test__type_without_purge__fails(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            [
                "playlist",
                "delete",
                str(uuid.uuid4()),
                "--email",
                "test@example.com",
                "--type",
                "discovery",
            ],
        )
        assert result.exit_code != 0
        assert "--type and --provider can only be used with --purge" in clean_typer_text(result.output)

    def test__provider_without_purge__fails(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            [
                "playlist",
                "delete",
                str(uuid.uuid4()),
                "--email",
                "test@example.com",
                "--provider",
                "spotify",
            ],
        )
        assert result.exit_code != 0
        assert "--type and --provider can only be used with --purge" in clean_typer_text(result.output)


class TestDeleteCommand:
    @pytest.fixture(autouse=True)
    def mock_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.delete_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = 1
            yield patched

    def test__single_delete__nominal(self, runner: CliRunner, mock_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["playlist", "delete", str(uuid.uuid4()), "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "Deleted 1 playlist(s)." in result.output
        mock_delete_logic.assert_called_once()

    def test__purge__with_yes_flag(self, runner: CliRunner, mock_delete_logic: mock.AsyncMock) -> None:
        mock_delete_logic.return_value = 3
        result = runner.invoke(app, ["playlist", "delete", "--purge", "--email", "test@example.com", "--yes"])
        assert result.exit_code == 0
        assert "Deleted 3 playlist(s)." in result.output

    def test__purge__confirmation_accepted(self, runner: CliRunner, mock_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["playlist", "delete", "--purge", "--email", "test@example.com"], input="y\n")
        assert result.exit_code == 0
        mock_delete_logic.assert_called_once()

    def test__purge__confirmation_declined(self, runner: CliRunner, mock_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["playlist", "delete", "--purge", "--email", "test@example.com"], input="n\n")
        assert result.exit_code != 0
        mock_delete_logic.assert_not_called()

    def test__purge__confirmation_message_includes_filters(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["playlist", "delete", "--purge", "--type", "discovery", "--email", "test@example.com"],
            input="n\n",
        )
        assert "type=discovery" in result.output

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_delete_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["playlist", "delete", str(uuid.uuid4()), "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__playlist_not_found(
        self,
        runner: CliRunner,
        mock_delete_logic: mock.AsyncMock,
    ) -> None:
        mock_delete_logic.side_effect = PlaylistNotFoundError()
        playlist_id = uuid.uuid4()
        result = runner.invoke(app, ["playlist", "delete", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code != 0
        assert f"Playlist {playlist_id} not found." in result.stderr

    def test__exception(
        self,
        runner: CliRunner,
        mock_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_delete_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["playlist", "delete", str(uuid.uuid4()), "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_playlist_repository")
class TestDeleteLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await delete_logic(
                email="unknown@example.com",  # type: ignore[arg-type]
                playlist_id=uuid.uuid4(),
                purge=False,
                type=None,
                provider=None,
            )

    async def test__single_delete__success(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_playlist_repository.delete.return_value = True
        playlist_id = uuid.uuid4()

        count = await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
            playlist_id=playlist_id,
            purge=False,
            type=None,
            provider=None,
        )

        assert count == 1
        mock_playlist_repository.delete.assert_called_once_with(
            user_id=mock_user_repository.get_by_email.return_value.id,
            playlist_id=playlist_id,
        )

    async def test__single_delete__not_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_playlist_repository.delete.return_value = False

        with pytest.raises(PlaylistNotFoundError):
            await delete_logic(
                email="test@example.com",  # type: ignore[arg-type]
                playlist_id=uuid.uuid4(),
                purge=False,
                type=None,
                provider=None,
            )

    async def test__single_delete__no_playlist_id__not_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        with pytest.raises(PlaylistNotFoundError):
            await delete_logic(
                email="test@example.com",  # type: ignore[arg-type]
                playlist_id=None,
                purge=False,
                type=None,
                provider=None,
            )

        mock_playlist_repository.delete.assert_not_awaited()

    async def test__purge__calls_repository_with_filters(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_playlist_repository.purge.return_value = 5

        count = await delete_logic(
            email="test@example.com",  # type: ignore[arg-type]
            playlist_id=None,
            purge=True,
            type=PlaylistType.DISCOVERY,
            provider=MusicProvider.SPOTIFY,
        )

        assert count == 5
        mock_playlist_repository.purge.assert_called_once_with(
            user_id=mock_user_repository.get_by_email.return_value.id,
            type=PlaylistType.DISCOVERY,
            provider=MusicProvider.SPOTIFY,
        )
