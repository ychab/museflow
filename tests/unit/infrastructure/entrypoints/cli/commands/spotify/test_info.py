from collections.abc import Iterable
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.spotify.info import SpotifyInfoData
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.factories.entities.auth import OAuthProviderUserTokenFactory
from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestSpotifyInfoParserCommand:
    @pytest.fixture(autouse=True)
    def mock_info_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.info.info_logic"
        with mock.patch(target_path, autospec=True) as patched:
            patched.return_value = SpotifyInfoData()
            yield patched.return_value

    def test__nominal(self, runner: CliRunner) -> None:
        # fmt: off
        result = runner.invoke(
            app,
            [
                "spotify",
                "info",
                "--email", "test@example.com",
                "--genres",
                "--token",
             ]
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
        result = runner.invoke(app, ["spotify", "info", "--email", email])
        assert result.exit_code != 0

        output = clean_typer_text(result.output)
        assert f"Invalid value for '--email': value is not a valid email address: {expected_msg}" in output


class TestSpotifyInfoCommand:
    @pytest.fixture(autouse=True)
    def mock_info_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.spotify.info.info_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__no_flags(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(
            app,
            ["spotify", "info", "--email", "test@example.com", "--no-genre", "--no-token"],
        )

        output = clean_typer_text(result.stderr)
        assert result.exit_code != 0
        assert "At least one --show flag must be provided." in output

    def test__user_not_found(
        self,
        runner: CliRunner,
        mock_info_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_info_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["spotify", "info", "--email", "test@example.com"])

        output = clean_typer_text(result.stderr)
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in output

    def test__output__exceptions(
        self,
        runner: CliRunner,
        mock_info_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_info_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["spotify", "info", "--email", "test@example.com"])
        assert result.exit_code != 0

        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output

    def test__genres__print__nominal(
        self,
        runner: CliRunner,
        mock_info_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_info_logic.return_value = SpotifyInfoData(genres=["rock", "pop"], token=None)
        result = runner.invoke(app, ["spotify", "info", "--email", "test@example.com", "--genres"])

        output = clean_typer_text(result.stdout)
        assert result.exit_code == 0
        assert "Genres available: - 'rock' - 'pop'" in output

    def test__genres__print__none(
        self,
        runner: CliRunner,
        mock_info_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_info_logic.return_value = SpotifyInfoData()
        result = runner.invoke(app, ["spotify", "info", "--email", "test@example.com", "--genres"])

        output = clean_typer_text(result.stdout)
        assert result.exit_code == 0
        assert "" in output

    def test__token__print__nominal(
        self,
        runner: CliRunner,
        mock_info_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        auth_token = OAuthProviderUserTokenFactory.build()
        mock_info_logic.return_value = SpotifyInfoData(genres=[], token=auth_token)
        result = runner.invoke(app, ["spotify", "info", "--email", "test@example.com", "--token"])

        output = clean_typer_text(result.stdout)
        assert result.exit_code == 0
        assert "Spotify Auth Token:" in output
        assert auth_token.token_access in output
        assert auth_token.token_refresh in output

    def test__token__print__none(
        self,
        runner: CliRunner,
        mock_info_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_info_logic.return_value = SpotifyInfoData()
        result = runner.invoke(app, ["spotify", "info", "--email", "test@example.com", "--token"])

        output = clean_typer_text(result.stdout)
        assert result.exit_code == 0
        assert output == ""
