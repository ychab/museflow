import uuid
from collections.abc import AsyncGenerator
from collections.abc import Iterable
from contextlib import asynccontextmanager
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.application.ports.providers.library import ProviderLibraryPort
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import PlaylistType
from museflow.domain.exceptions import PlaylistNotFoundError
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.playlist.delete import playlist_delete_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.playlist import PlaylistFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.playlist.delete"


class TestPlaylistDeleteParserCommand:
    @pytest.fixture(autouse=True)
    def mock_playlist_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.playlist_delete_logic", new_callable=mock.AsyncMock) as patched:
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


class TestPlaylistDeleteCommand:
    @pytest.fixture(autouse=True)
    def mock_playlist_delete_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.playlist_delete_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = 1
            yield patched

    def test__single_delete__nominal(self, runner: CliRunner, mock_playlist_delete_logic: mock.AsyncMock) -> None:
        result = runner.invoke(app, ["playlist", "delete", str(uuid.uuid4()), "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "Deleted 1 playlist(s) of test@example.com." in result.output
        mock_playlist_delete_logic.assert_called_once()

    def test__purge__with_yes_flag(self, runner: CliRunner, mock_playlist_delete_logic: mock.AsyncMock) -> None:
        mock_playlist_delete_logic.return_value = 3
        result = runner.invoke(app, ["playlist", "delete", "--purge", "--email", "test@example.com", "--yes"])
        assert result.exit_code == 0
        assert "Deleted 3 playlist(s) of test@example.com." in result.output

    def test__purge__confirmation_accepted(
        self, runner: CliRunner, mock_playlist_delete_logic: mock.AsyncMock
    ) -> None:
        result = runner.invoke(app, ["playlist", "delete", "--purge", "--email", "test@example.com"], input="y\n")
        assert result.exit_code == 0
        mock_playlist_delete_logic.assert_called_once()

    def test__purge__confirmation_declined(
        self, runner: CliRunner, mock_playlist_delete_logic: mock.AsyncMock
    ) -> None:
        result = runner.invoke(app, ["playlist", "delete", "--purge", "--email", "test@example.com"], input="n\n")
        assert result.exit_code != 0
        mock_playlist_delete_logic.assert_not_called()

    def test__purge__confirmation_message_includes_filters(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["playlist", "delete", "--purge", "--type", "discovery", "--email", "test@example.com"],
            input="n\n",
        )
        assert "About to delete ALL playlists (type=discovery) of test@example.com." in result.output

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_playlist_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_delete_logic.side_effect = UserNotFoundError()
        result = runner.invoke(app, ["playlist", "delete", str(uuid.uuid4()), "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__playlist_not_found(
        self,
        runner: CliRunner,
        mock_playlist_delete_logic: mock.AsyncMock,
    ) -> None:
        mock_playlist_delete_logic.side_effect = PlaylistNotFoundError()
        playlist_id = uuid.uuid4()
        result = runner.invoke(app, ["playlist", "delete", str(playlist_id), "--email", "test@example.com"])
        assert result.exit_code != 0
        assert f"Playlist {playlist_id} not found." in result.stderr

    def test__auth_token_not_found(
        self,
        runner: CliRunner,
        mock_playlist_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_delete_logic.side_effect = ProviderAuthTokenNotFoundError()
        result = runner.invoke(
            app,
            ["playlist", "delete", str(uuid.uuid4()), "--email", "test@example.com", "--include-remote"],
        )
        assert result.exit_code != 0
        assert "Auth token not found for test@example.com" in clean_typer_text(result.stderr)

    def test__exception(
        self,
        runner: CliRunner,
        mock_playlist_delete_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_playlist_delete_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["playlist", "delete", str(uuid.uuid4()), "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures(
    "mock_get_unit_of_work",
    "mock_user_repository",
    "mock_playlist_repository",
    "mock_get_provider_library",
)
class TestPlaylistDeleteLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    @pytest.fixture
    def provider_libraries(self) -> dict[str, mock.AsyncMock]:
        return {
            MusicProvider.SPOTIFY: mock.AsyncMock(spec=ProviderLibraryPort),
            "foo": mock.AsyncMock(spec=ProviderLibraryPort),
        }

    @pytest.fixture
    def mock_get_provider_libraries(self, provider_libraries: dict[str, mock.AsyncMock]) -> Iterable[mock.Mock]:
        @asynccontextmanager
        async def _get_provider_library(provider: str, **_: object) -> AsyncGenerator[mock.AsyncMock]:
            yield provider_libraries[provider]

        with mock.patch(f"{TARGET_PATH}.get_provider_library", side_effect=_get_provider_library) as patched:
            yield patched

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFoundError):
            await playlist_delete_logic(
                email="unknown@example.com",
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

        count = await playlist_delete_logic(
            email="test@example.com",
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
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_playlist_repository.delete.return_value = False

        with pytest.raises(PlaylistNotFoundError):
            await playlist_delete_logic(
                email="test@example.com",
                playlist_id=uuid.uuid4(),
                purge=False,
                type=None,
                provider=None,
            )

    async def test__purge__calls_repository_with_filters(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_playlist_repository: mock.AsyncMock,
    ) -> None:
        mock_playlist_repository.purge.return_value = 5

        count = await playlist_delete_logic(
            email="test@example.com",
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

    async def test__include_remote__success(
        self,
        mock_playlist_repository: mock.AsyncMock,
        mock_provider_library: mock.AsyncMock,
    ) -> None:
        playlist = PlaylistFactory.build()
        mock_playlist_repository.get.return_value = playlist
        mock_playlist_repository.delete.return_value = True

        count = await playlist_delete_logic(
            email="test@example.com",
            playlist_id=playlist.id,
            purge=False,
            type=None,
            provider=None,
            include_remote=True,
        )

        assert count == 1
        mock_provider_library.delete_playlist.assert_awaited_once_with(playlist.provider_id)

    async def test__include_remote__not_found__no_library_built(
        self,
        mock_playlist_repository: mock.AsyncMock,
        mock_get_provider_libraries: mock.Mock,
    ) -> None:
        mock_playlist_repository.get.return_value = None

        with pytest.raises(PlaylistNotFoundError):
            await playlist_delete_logic(
                email="test@example.com",
                playlist_id=uuid.uuid4(),
                purge=False,
                type=None,
                provider=None,
                include_remote=True,
            )

        mock_get_provider_libraries.assert_not_called()

    async def test__purge__include_remote__one_library_per_provider(
        self,
        mock_playlist_repository: mock.AsyncMock,
        mock_get_provider_libraries: mock.Mock,
        provider_libraries: dict[str, mock.AsyncMock],
    ) -> None:
        spotify_playlists = PlaylistFactory.batch(2, provider=MusicProvider.SPOTIFY)
        other_playlist = PlaylistFactory.build(provider="foo")
        mock_playlist_repository.list.return_value = [*spotify_playlists, other_playlist]

        count = await playlist_delete_logic(
            email="test@example.com",
            playlist_id=None,
            purge=True,
            type=None,
            provider=None,
            include_remote=True,
        )

        assert count == 3
        assert mock_get_provider_libraries.call_count == 2
        assert provider_libraries[MusicProvider.SPOTIFY].delete_playlist.await_count == 2
        provider_libraries["foo"].delete_playlist.assert_awaited_once_with(other_playlist.provider_id)
