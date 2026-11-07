from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import TasteProfileNotFoundError
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.taste.view import generate_profile_html_content
from museflow.infrastructure.entrypoints.cli.commands.taste.view import taste_view_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.taste import TasteProfileDataFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestTasteViewParserCommand:
    @pytest.fixture(autouse=True)
    def mock_taste_view_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.view.taste_view_logic"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = TasteProfileFactory.build()
            yield patched

    @pytest.fixture(autouse=True)
    def mock_typer_launch(self) -> Iterable[mock.Mock]:
        with mock.patch("museflow.infrastructure.entrypoints.cli.commands.taste.view.webbrowser.open") as patched:
            yield patched

    def test__nominal(self, runner: CliRunner, mock_typer_launch: mock.Mock) -> None:
        result = runner.invoke(
            app,
            ["taste", "view", "--email", "test@example.com", "--name", "my-profile"],
        )
        assert result.exit_code == 0
        mock_typer_launch.assert_not_called()

    def test__nominal__format_json(self, runner: CliRunner, mock_typer_launch: mock.Mock) -> None:
        result = runner.invoke(
            app,
            ["taste", "view", "--email", "test@example.com", "--name", "my-profile", "--format", "json"],
        )
        assert result.exit_code == 0
        mock_typer_launch.assert_not_called()

    def test__nominal__format_python(self, runner: CliRunner, mock_typer_launch: mock.Mock) -> None:
        result = runner.invoke(
            app,
            ["taste", "view", "--email", "test@example.com", "--name", "my-profile", "--format", "python"],
        )
        assert result.exit_code == 0
        mock_typer_launch.assert_not_called()

    def test__nominal__format_html(self, runner: CliRunner, mock_typer_launch: mock.Mock) -> None:
        result = runner.invoke(
            app,
            ["taste", "view", "--email", "test@example.com", "--name", "my-profile", "--format", "html"],
        )
        assert result.exit_code == 0
        mock_typer_launch.assert_called_once()

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
        result = runner.invoke(app, ["taste", "view", "--email", email])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output


class TestTasteViewCommand:
    @pytest.fixture(autouse=True)
    def mock_taste_view_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.view.taste_view_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_taste_view_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_taste_view_logic.side_effect = UserNotFoundError()

        result = runner.invoke(app, ["taste", "view", "--email", "test@example.com", "--name", "my-profile"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__profile_not_found(
        self,
        mock_taste_view_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_taste_view_logic.side_effect = TasteProfileNotFoundError()

        result = runner.invoke(app, ["taste", "view", "--email", "test@example.com", "--name", "my-profile"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Taste profile not found with name: my-profile" in output

    def test__generic_exception(
        self,
        mock_taste_view_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_taste_view_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["taste", "view", "--email", "test@example.com", "--name", "my-profile"])
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures(
    "mock_get_unit_of_work",
    "mock_user_repository",
    "mock_taste_profile_repository",
)
class TestTasteViewLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.taste.view"

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await taste_view_logic(email="test@example.com", name="my-profile")


class TestGenerateProfileHtmlContent:
    def test__escapes_profile_text(self) -> None:
        script = "<script>alert(1)</script>"
        taste_profile = TasteProfileFactory.build(
            name=script,
            profile=TasteProfileDataFactory.build(
                personality_archetype=script,
                life_phase_insights=[script],
                core_identity={script: 0.5},
            ),
            profiler_metadata={"steps": {"reflect": {"model": script}}},
        )

        content = generate_profile_html_content(taste_profile)

        assert "<script>" not in content
        assert content.count("&lt;script&gt;alert(1)&lt;/script&gt;") == 5
