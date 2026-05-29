from collections.abc import Iterable
from pathlib import Path
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste.export import export_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.entities.user import UserFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestTasteExportParserCommand:
    @pytest.fixture(autouse=True)
    def mock_export_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.export.export_logic"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = TasteProfileFactory.build()
            yield patched

    @pytest.fixture(autouse=True)
    def mock_yaml_dump(self) -> Iterable[mock.Mock]:
        with mock.patch("museflow.infrastructure.entrypoints.cli.commands.taste.export.yaml.safe_dump") as patched:
            yield patched

    @pytest.fixture(autouse=True)
    def mock_path_open(self) -> Iterable[mock.Mock]:
        with mock.patch("pathlib.Path.open", mock.mock_open()) as patched:
            yield patched

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
        result = runner.invoke(app, ["taste", "export", "--email", email])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output


class TestTasteExportCommand:
    @pytest.fixture(autouse=True)
    def mock_export_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.export.export_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_export_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_export_logic.side_effect = UserNotFound()

        result = runner.invoke(
            app,
            [
                "taste",
                "export",
                "--email",
                "test@example.com",
                "--name",
                "my-profile",
                "--output",
                str(tmp_path / "out.yaml"),
            ],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__profile_not_found(
        self,
        mock_export_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_export_logic.side_effect = TasteProfileNotFoundException()

        result = runner.invoke(
            app,
            [
                "taste",
                "export",
                "--email",
                "test@example.com",
                "--name",
                "my-profile",
                "--output",
                str(tmp_path / "out.yaml"),
            ],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Taste profile not found with name: my-profile" in output

    def test__generic_exception(
        self,
        mock_export_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_export_logic.side_effect = Exception("Boom")

        result = runner.invoke(
            app,
            [
                "taste",
                "export",
                "--email",
                "test@example.com",
                "--name",
                "my-profile",
                "--output",
                str(tmp_path / "out.yaml"),
            ],
        )
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__nominal(
        self,
        mock_export_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        taste_profile = TasteProfileFactory.build(name="my-profile")
        mock_export_logic.return_value = taste_profile
        output_path = tmp_path / "out.yaml"

        result = runner.invoke(
            app,
            ["taste", "export", "--email", "test@example.com", "--name", "my-profile", "--output", str(output_path)],
        )
        assert result.exit_code == 0
        assert output_path.exists()
        assert "my-profile" in result.output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_taste_profile_repository",
)
class TestTasteExportLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.taste.export"

    async def test__nominal(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        taste_profile = TasteProfileFactory.build()
        mock_user_repository.get_by_email.return_value = UserFactory.build()
        mock_taste_profile_repository.get.return_value = taste_profile

        result = await export_logic(email="test@example.com", name="my-profile")

        assert isinstance(result, TasteProfile)
        assert result == taste_profile

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await export_logic(email="test@example.com", name="my-profile")

    async def test__profile__not_found(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = UserFactory.build()
        mock_taste_profile_repository.get.return_value = None

        with pytest.raises(TasteProfileNotFoundException):
            await export_logic(email="test@example.com", name="my-profile")
