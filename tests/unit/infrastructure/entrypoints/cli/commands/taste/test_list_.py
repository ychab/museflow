from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste.list_ import list_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.entities.user import UserFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.taste.list_"


class TestListParserCommand:
    @pytest.fixture(autouse=True)
    def mock_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.list_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = []
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["taste", "list", "--email", "test@example.com"])
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
        result = runner.invoke(app, ["taste", "list", "--email", email])
        assert result.exit_code != 0
        assert expected_msg in clean_typer_text(result.output)


class TestListCommand:
    @pytest.fixture(autouse=True)
    def mock_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.list_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = []
            yield patched

    def test__empty(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["taste", "list", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "No taste profiles found" in result.output

    def test__with_profiles(self, runner: CliRunner, mock_logic: mock.AsyncMock) -> None:
        profile = TasteProfileFactory.build(name="my-profile", tracks_count=42)
        mock_logic.return_value = [profile]

        result = runner.invoke(app, ["taste", "list", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "my-profile" in result.output
        assert "42" in result.output

    def test__user_not_found(
        self, runner: CliRunner, mock_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["taste", "list", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__exception(self, runner: CliRunner, mock_logic: mock.AsyncMock, clean_typer_text: TextCleaner) -> None:
        mock_logic.side_effect = Exception("Boom")
        result = runner.invoke(app, ["taste", "list", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_taste_profile_repository")
class TestListLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await list_logic(email="unknown@example.com")  # type: ignore[arg-type]

    async def test__nominal(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        profiles = TasteProfileFactory.batch(2)
        mock_user_repository.get_by_email.return_value = user
        mock_taste_profile_repository.list.return_value = profiles

        result = await list_logic(email=user.email)  # type: ignore[arg-type]

        assert result == profiles
        mock_taste_profile_repository.list.assert_called_once_with(user_id=user.id)
