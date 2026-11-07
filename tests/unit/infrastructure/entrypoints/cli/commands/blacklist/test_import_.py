from collections.abc import Iterable
from pathlib import Path
from typing import Final
from unittest import mock

from pydantic import ValidationError

import pytest
from typer.testing import CliRunner

from museflow.application.use_cases.blacklist_import import ImportBlacklistResult
from museflow.domain.exceptions import UserNotFoundError
from museflow.infrastructure.entrypoints.cli.commands.blacklist.import_ import blacklist_import_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.user import UserFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.blacklist.import_"


@pytest.fixture
def blacklist_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "blacklist.yaml"
    path.write_text("artists:\n  - artist_name: Some Artist\n")
    return path


class TestBlacklistImportParserCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_import_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_import_logic", autospec=True) as patched:
            patched.return_value = ImportBlacklistResult(
                imported_artists_count=0,
                imported_tracks_count=0,
                skipped_count=0,
            )
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
        blacklist_yaml: Path,
    ) -> None:
        result = runner.invoke(app, ["blacklist", "import", "--email", email, "--input", str(blacklist_yaml)])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output


class TestBlacklistImportCommand:
    @pytest.fixture(autouse=True)
    def mock_blacklist_import_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.blacklist_import_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__user_not_found(
        self,
        mock_blacklist_import_logic: mock.AsyncMock,
        runner: CliRunner,
        blacklist_yaml: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_blacklist_import_logic.side_effect = UserNotFoundError()

        result = runner.invoke(
            app,
            ["blacklist", "import", "--email", "test@example.com", "--input", str(blacklist_yaml)],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__generic_exception(
        self,
        mock_blacklist_import_logic: mock.AsyncMock,
        runner: CliRunner,
        blacklist_yaml: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_blacklist_import_logic.side_effect = Exception("Boom")

        result = runner.invoke(
            app,
            ["blacklist", "import", "--email", "test@example.com", "--input", str(blacklist_yaml)],
        )
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__nominal(
        self,
        mock_blacklist_import_logic: mock.AsyncMock,
        runner: CliRunner,
        blacklist_yaml: Path,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_blacklist_import_logic.return_value = ImportBlacklistResult(
            imported_artists_count=2,
            imported_tracks_count=1,
            skipped_count=4,
        )

        result = runner.invoke(
            app,
            ["blacklist", "import", "--email", "test@example.com", "--input", str(blacklist_yaml)],
        )
        assert result.exit_code == 0

        output = clean_typer_text(result.output)
        assert "Imported 2 artist(s) and 1 track(s) (4 already blacklisted)." in output
        assert mock_blacklist_import_logic.call_args.kwargs["data"] == {"artists": [{"artist_name": "Some Artist"}]}


@pytest.mark.usefixtures(
    "mock_get_unit_of_work",
    "mock_user_repository",
    "mock_blacklist_repository",
)
class TestBlacklistImportLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(None, id="empty_file"),
            pytest.param([{"artist_name": "Some Artist"}], id="list"),
            pytest.param({"artists": [{"artist_name": ""}]}, id="empty_name"),
            pytest.param({"tracks": [{"name": "Some Track"}]}, id="missing_artist"),
        ],
    )
    async def test__invalid_data(self, mock_user_repository: mock.AsyncMock, data: object) -> None:
        mock_user_repository.get_by_email.return_value = UserFactory.build()

        with pytest.raises(ValidationError):
            await blacklist_import_logic(email="test@example.com", data=data)

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFoundError):
            await blacklist_import_logic(email="test@example.com", data={})
