from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import UserNotFound
from museflow.domain.value_objects.blacklist import UserBlacklist
from museflow.infrastructure.entrypoints.cli.commands.blacklist.list_ import list_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.blacklist import BlacklistedArtistFactory
from tests.unit.factories.entities.blacklist import BlacklistedTrackFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.blacklist.list_"


class TestListParserCommand:
    @pytest.fixture(autouse=True)
    def mock_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.list_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = UserBlacklist()
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["blacklist", "list", "--email", "test@example.com"])
        assert result.exit_code == 0

    @pytest.mark.parametrize(
        ("email", "expected_msg"),
        [
            pytest.param("testtest.com", "An email address must have an @-sign", id="missing_@"),
            pytest.param("test@test", "The part after the @-sign is not valid", id="missing_dot"),
        ],
    )
    def test__email__invalid(
        self, runner: CliRunner, email: str, expected_msg: str, clean_typer_text: TextCleaner
    ) -> None:
        result = runner.invoke(app, ["blacklist", "list", "--email", email])
        assert result.exit_code != 0
        assert expected_msg in clean_typer_text(result.output)


class TestListCommand:
    @pytest.fixture(autouse=True)
    def mock_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.list_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = UserBlacklist()
            yield patched

    def test__empty_blacklist(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["blacklist", "list", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "empty" in result.output

    def test__with_artists_and_tracks(self, runner: CliRunner, mock_logic: mock.AsyncMock) -> None:
        artist = BlacklistedArtistFactory.build(artist_name="Taylor Swift")
        track = BlacklistedTrackFactory.build(name="Shake It Off", artist_name="Taylor Swift")
        mock_logic.return_value = UserBlacklist(artists=[artist], tracks=[track])

        result = runner.invoke(app, ["blacklist", "list", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "Taylor Swift" in result.output
        assert "Shake It Off" in result.output

    def test__user_not_found(
        self, runner: CliRunner, mock_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["blacklist", "list", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exceptions(self, runner: CliRunner, mock_logic: mock.AsyncMock, clean_typer_text: TextCleaner) -> None:
        mock_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["blacklist", "list", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_blacklist_repository")
class TestListLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await list_logic(email="unknown@example.com")  # type: ignore[arg-type]
