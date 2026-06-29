from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.enrich.tracks import EnrichTracksReport
from museflow.infrastructure.entrypoints.cli.commands.enrich.tracks import enrich_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.enrich.tracks"


class TestEnrichTracksParserCommand:
    @pytest.fixture(autouse=True)
    def mock_enrich_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.enrich_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = EnrichTracksReport(enriched_count=0, error_count=0)
            yield patched

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["enrich", "tracks", "--email", "notanemail"])
        assert result.exit_code != 0
        assert "An email address must have an @-sign" in clean_typer_text(result.output)

    def test__batch_size__defaults_to_200(self, runner: CliRunner, mock_enrich_logic: mock.AsyncMock) -> None:
        runner.invoke(app, ["enrich", "tracks", "--email", "test@example.com"])
        call_kwargs = mock_enrich_logic.call_args.kwargs
        assert call_kwargs["batch_size"] == 200

    def test__limit__optional(self, runner: CliRunner, mock_enrich_logic: mock.AsyncMock) -> None:
        runner.invoke(app, ["enrich", "tracks", "--email", "test@example.com"])
        call_kwargs = mock_enrich_logic.call_args.kwargs
        assert call_kwargs["limit"] is None

    def test__force__defaults_to_false(self, runner: CliRunner, mock_enrich_logic: mock.AsyncMock) -> None:
        runner.invoke(app, ["enrich", "tracks", "--email", "test@example.com"])
        call_kwargs = mock_enrich_logic.call_args.kwargs
        assert call_kwargs["force"] is False


class TestEnrichTracksCommand:
    @pytest.fixture(autouse=True)
    def mock_enrich_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.enrich_logic", new_callable=mock.AsyncMock) as patched:
            patched.return_value = EnrichTracksReport(enriched_count=5, error_count=0)
            yield patched

    def test__nominal(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["enrich", "tracks", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "Enriched 5 track(s)" in result.output

    def test__no_tracks(self, runner: CliRunner, mock_enrich_logic: mock.AsyncMock) -> None:
        mock_enrich_logic.return_value = EnrichTracksReport(enriched_count=0, error_count=0)
        result = runner.invoke(app, ["enrich", "tracks", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "No tracks to enrich" in result.output

    def test__error_count__shows_warning(self, runner: CliRunner, mock_enrich_logic: mock.AsyncMock) -> None:
        mock_enrich_logic.return_value = EnrichTracksReport(enriched_count=3, error_count=2)
        result = runner.invoke(app, ["enrich", "tracks", "--email", "test@example.com"])
        assert result.exit_code == 0
        assert "2 batch(es) failed" in result.output

    def test__user_not_found(
        self, runner: CliRunner, mock_enrich_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_enrich_logic.side_effect = UserNotFound()
        result = runner.invoke(app, ["enrich", "tracks", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "User not found with email: test@example.com" in clean_typer_text(result.output)

    def test__generic_exception(
        self, runner: CliRunner, mock_enrich_logic: mock.AsyncMock, clean_typer_text: TextCleaner
    ) -> None:
        mock_enrich_logic.side_effect = Exception("Gemini down")
        result = runner.invoke(app, ["enrich", "tracks", "--email", "test@example.com"])
        assert result.exit_code != 0
        assert "Error: Gemini down" in clean_typer_text(result.stderr)


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_track_repository", "mock_gemini_enricher")
class TestEnrichTracksLogic:
    TARGET_PATH: Final[str] = TARGET_PATH

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None
        with pytest.raises(UserNotFound):
            await enrich_logic(email="unknown@example.com")  # type: ignore[arg-type]

    async def test__passes_config_to_use_case(
        self,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_track_repository.get_list.return_value = []

        await enrich_logic(
            email="test@example.com",  # type: ignore[arg-type]
            force=True,
            batch_size=10,
            limit=100,
        )

        mock_track_repository.get_list.assert_awaited_once_with(
            user_id=mock_user_repository.get_by_email.return_value.id,
            unenriched_only=False,
            limit=100,
        )
