import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from typing import Final
from unittest import mock

from pydantic import TypeAdapter
from pydantic import ValidationError

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste.import_ import import_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.factories.entities.user import UserFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestTasteImportParserCommand:
    @pytest.fixture(autouse=True)
    def mock_import_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.import_.import_logic"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = TasteProfileFactory.build()
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
        result = runner.invoke(app, ["taste", "import", "--email", email])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output


class TestTasteImportCommand:
    @pytest.fixture(autouse=True)
    def mock_import_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.import_.import_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__file_not_found(
        self,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["taste", "import", "--email", "test@example.com", "--input", "/nonexistent/path/profile.yaml"],
        )
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "File not found" in output

    def test__yaml_parse_error(
        self,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [unclosed\n")

        result = runner.invoke(
            app,
            ["taste", "import", "--email", "test@example.com", "--input", str(bad_yaml)],
        )
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Invalid YAML" in output

    def test__user_not_found(
        self,
        mock_import_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_import_logic.side_effect = UserNotFound()
        valid_yaml = tmp_path / "profile.yaml"
        valid_yaml.write_text("name: test-profile\n")

        result = runner.invoke(
            app,
            ["taste", "import", "--email", "test@example.com", "--input", str(valid_yaml)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_import_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_import_logic.side_effect = Exception("Boom")
        valid_yaml = tmp_path / "profile.yaml"
        valid_yaml.write_text("name: test-profile\n")

        result = runner.invoke(
            app,
            ["taste", "import", "--email", "test@example.com", "--input", str(valid_yaml)],
        )
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__nominal(
        self,
        mock_import_logic: mock.AsyncMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        taste_profile = TasteProfileFactory.build(name="my-profile")
        mock_import_logic.return_value = taste_profile
        valid_yaml = tmp_path / "profile.yaml"
        valid_yaml.write_text("name: my-profile\n")

        result = runner.invoke(
            app,
            ["taste", "import", "--email", "test@example.com", "--input", str(valid_yaml)],
        )
        assert result.exit_code == 0
        assert "my-profile" in result.output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_taste_profile_repository",
)
class TestTasteImportLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.taste.import_"

    async def test__nominal(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        original_profile = TasteProfileFactory.build()
        profile_data: dict[str, Any] = TypeAdapter(TasteProfile).dump_python(original_profile, mode="json")

        mock_user_repository.get_by_email.return_value = user
        mock_taste_profile_repository.upsert.return_value = TasteProfileFactory.build(user_id=user.id)

        result = await import_logic(email="test@example.com", data=profile_data)

        upserted: TasteProfile = mock_taste_profile_repository.upsert.call_args[0][0]
        assert upserted.user_id == user.id
        assert upserted.id != original_profile.id
        assert isinstance(result, TasteProfile)

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await import_logic(email="test@example.com", data={})

    async def test__invalid_data(
        self,
        mock_user_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = UserFactory.build()

        with pytest.raises(ValidationError):
            await import_logic(email="test@example.com", data={"invalid": "data"})

    async def test__new_id_generated_each_call(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_taste_profile_repository: mock.AsyncMock,
    ) -> None:
        user = UserFactory.build()
        original_profile = TasteProfileFactory.build()
        profile_data: dict[str, Any] = TypeAdapter(TasteProfile).dump_python(original_profile, mode="json")

        mock_user_repository.get_by_email.return_value = user
        mock_taste_profile_repository.upsert.side_effect = lambda p: p

        await import_logic(email="test@example.com", data=profile_data)
        first_id: uuid.UUID = mock_taste_profile_repository.upsert.call_args[0][0].id

        await import_logic(email="test@example.com", data=profile_data)
        second_id: uuid.UUID = mock_taste_profile_repository.upsert.call_args[0][0].id

        assert first_id != second_id
        assert first_id != original_profile.id
        assert second_id != original_profile.id
