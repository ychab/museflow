import dataclasses
from collections.abc import Iterable
from typing import Any
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileNoSeedException
from museflow.domain.exceptions import UserNotFound
from museflow.domain.types import TasteProfiler
from museflow.infrastructure.entrypoints.cli.commands.taste.build import build_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.taste import TasteProfileDataFactory
from tests.unit.factories.entities.taste import TasteProfileFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestTasteBuildParserCommand:
    @pytest.fixture(autouse=True)
    def mock_build_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.build.build_logic"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = TasteProfileFactory.build()
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "taste",
                "build",
                "--email", "test@example.com",
                "--name", "my-profile",
                "--track-limit", "3000",
                "--batch-size", "40",
            ],
        )
        # fmt: on
        assert result.exit_code == 0

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
        result = runner.invoke(app, ["taste", "build", "--email", email])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output

    @pytest.mark.parametrize(
        ("batch_size", "expected_msg"),
        [
            pytest.param(0, "0 is not in the range", id="zero"),
            pytest.param(1001, "1001 is not in the range", id="max_exceed"),
            pytest.param("foo", "'foo' is not a valid integer", id="string"),
        ],
    )
    def test__batch_size__invalid(
        self,
        runner: CliRunner,
        batch_size: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["taste", "build", "--email", "test@example.com", "--batch-size", batch_size],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--batch-size': {expected_msg}" in output

    @pytest.mark.parametrize(
        ("track_limit", "expected_msg"),
        [
            pytest.param(0, "0 is not in the range", id="zero"),
            pytest.param(50000, "50000 is not in the range", id="max_exceed"),
            pytest.param("foo", "'foo' is not a valid integer", id="string"),
        ],
    )
    def test__track_limit__invalid(
        self,
        runner: CliRunner,
        track_limit: Any,
        expected_msg: str,
        clean_typer_text: TextCleaner,
    ) -> None:
        result = runner.invoke(
            app,
            ["taste", "build", "--email", "test@example.com", "--track-limit", track_limit],
        )
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--track-limit': {expected_msg}" in output


class TestTasteBuildCommand:
    @pytest.fixture(autouse=True)
    def mock_build_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.taste.build.build_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    @pytest.fixture
    def taste_profile(self, request: pytest.FixtureRequest) -> TasteProfile:
        # @TODO - @FIXME - Polyfactory don't allow field override with TypedDict!?
        field_overrides = getattr(request, "param", {})
        profile = TasteProfileFactory.build()

        profile_data = TasteProfileDataFactory.build()
        profile_data.update(field_overrides)  # type: ignore[typeddict-item]

        return dataclasses.replace(profile, profile=profile_data)

    def test__user_not_found(
        self,
        mock_build_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_build_logic.side_effect = UserNotFound()

        result = runner.invoke(app, ["taste", "build", "--email", "test@example.com", "--name", "my-profile"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "User not found with email: test@example.com" in output

    def test__no_seeds(
        self,
        mock_build_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_build_logic.side_effect = TasteProfileNoSeedException()

        result = runner.invoke(app, ["taste", "build", "--email", "test@example.com", "--name", "my-profile"])
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "No tracks found for this user" in output

    def test__generic_exception(
        self,
        mock_build_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_build_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["taste", "build", "--email", "test@example.com", "--name", "my-profile"])
        assert result.exit_code == 1

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    @pytest.mark.parametrize(
        "taste_profile",
        [
            {
                "personality_archetype": "Dark Metal Wanderer",
                "life_phase_insights": ["You explore melancholy soundscapes"],
            }
        ],
        indirect=True,
    )
    def test__output__with_archetype(
        self,
        mock_build_logic: mock.AsyncMock,
        runner: CliRunner,
        taste_profile: TasteProfile,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_build_logic.return_value = taste_profile

        result = runner.invoke(app, ["taste", "build", "--email", "test@example.com", "--name", "my-profile"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Taste profile built:" in output
        assert "Dark Metal Wanderer" in output

    @pytest.mark.parametrize(
        "taste_profile",
        [
            {
                "personality_archetype": None,
                "life_phase_insights": [],
            }
        ],
        indirect=True,
    )
    def test__output__without_archetype(
        self,
        mock_build_logic: mock.AsyncMock,
        runner: CliRunner,
        taste_profile: TasteProfile,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_build_logic.return_value = taste_profile

        result = runner.invoke(app, ["taste", "build", "--email", "test@example.com", "--name", "my-profile"])
        assert result.exit_code == 0

        output = clean_typer_text(result.stdout)
        assert "Taste profile built:" in output
        assert "Archetype:" not in output


@pytest.mark.usefixtures(
    "mock_get_db",
    "mock_user_repository",
    "mock_track_repository",
    "mock_taste_profile_repository",
    "mock_gemini_profiler",
)
class TestTasteBuildLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.taste.build"

    async def test__user__not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await build_logic(
                email="test@example.com",
                profiler=TasteProfiler.GEMINI,
                name="my-profile",
                track_limit=3000,
                batch_size=200,
                sleep_seconds=0.0,
            )
