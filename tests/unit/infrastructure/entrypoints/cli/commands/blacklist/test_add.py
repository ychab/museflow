from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.blacklist.add import blacklist_add_artist_logic
from museflow.infrastructure.entrypoints.cli.commands.blacklist.add import blacklist_add_track_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.blacklist import BlacklistedArtistFactory
from tests.unit.factories.entities.blacklist import BlacklistedTrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.blacklist.add"


class TestBlacklistAddArtistParserCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_add_artist_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_add_artist_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = []
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["blacklist", "add-artist", "--email", "test@example.com", "Taylor Swift"])
        assert result.exit_code == 0

    @pytest.mark.parametrize(
        ("email", "expected_msg"),
        [
            pytest.param("testtest.com", "An email address must have an @-sign", id="missing_@"),
            pytest.param("test@test", "The part after the @-sign is not valid", id="missing_dot"),
        ],
    )
    def test__email__invalid(
        self,
        runner: CliRunner,
        email: str,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(app, ["blacklist", "add-artist", "--email", email, "Taylor Swift"])
        assert result.exit_code != 0
        assert expected_msg in clean_typer_text(result.output)


class TestBlacklistAddArtistCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_add_artist_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_add_artist_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner, mock_blacklist_add_artist_logic: mock.AsyncMock) -> None:
        entry = BlacklistedArtistFactory.build(artist_name="Taylor Swift")
        mock_blacklist_add_artist_logic.return_value = [entry]
        result = runner.invoke(app, ["blacklist", "add-artist", "--email", "test@example.com", "Taylor Swift"])
        assert result.exit_code == 0
        assert "Taylor Swift" in result.output

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_blacklist_add_artist_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_blacklist_add_artist_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["blacklist", "add-artist", "--email", "test@example.com", "Taylor Swift"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exceptions(
        self, runner: CliRunner, mock_blacklist_add_artist_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_blacklist_add_artist_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["blacklist", "add-artist", "--email", "test@example.com", "Taylor Swift"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_unit_of_work", "mock_user_repository", "mock_blacklist_repository")
class TestBlacklistAddArtistLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await blacklist_add_artist_logic(email="unknown@example.com", artist_names=["Taylor Swift"])


class TestBlacklistAddTrackParserCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_add_track_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_add_track_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = BlacklistedTrackFactory.build()
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        result = runner.invoke(
            app,
            ["blacklist", "add-track", "--email", "test@example.com", "Shake It Off", "--artist", "Taylor Swift"],
        )
        assert result.exit_code == 0

    @pytest.mark.parametrize(
        ("email", "expected_msg"),
        [
            pytest.param("testtest.com", "An email address must have an @-sign", id="missing_@"),
            pytest.param("test@test", "The part after the @-sign is not valid", id="missing_dot"),
        ],
    )
    def test__email__invalid(
        self,
        runner: CliRunner,
        email: str,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["blacklist", "add-track", "--email", email, "Shake It Off", "--artist", "Taylor Swift"],
        )
        assert result.exit_code != 0
        assert expected_msg in clean_typer_text(result.output)


class TestBlacklistAddTrackCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_add_track_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_add_track_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, runner: CliRunner, mock_blacklist_add_track_logic: mock.AsyncMock) -> None:
        entry = BlacklistedTrackFactory.build(name="Shake It Off", artist_name="Taylor Swift")
        mock_blacklist_add_track_logic.return_value = entry
        result = runner.invoke(
            app,
            ["blacklist", "add-track", "--email", "test@example.com", "Shake It Off", "--artist", "Taylor Swift"],
        )
        assert result.exit_code == 0
        assert "Shake It Off" in result.output

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_blacklist_add_track_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_blacklist_add_track_logic.side_effect = UserNotFound()
        result = runner.invoke(
            app,
            ["blacklist", "add-track", "--email", "test@example.com", "Shake It Off", "--artist", "Taylor Swift"],
        )
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exceptions(
        self, runner: CliRunner, mock_blacklist_add_track_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_blacklist_add_track_logic.side_effect = Exception("Boom")
        result = runner.invoke(
            app,
            ["blacklist", "add-track", "--email", "test@example.com", "Shake It Off", "--artist", "Taylor Swift"],
        )
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_unit_of_work", "mock_user_repository", "mock_blacklist_repository")
class TestBlacklistAddTrackLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await blacklist_add_track_logic(
                email="unknown@example.com", name="Shake It Off", artist_name="Taylor Swift"
            )
