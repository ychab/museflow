import uuid
from collections.abc import Iterable
from typing import Final
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.domain.entities.user import User
from museflow.domain.exceptions import RateScoreInvalidException
from museflow.domain.exceptions import TrackNotFoundError
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.rate.track import rate_track_logic
from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner

TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate.track"


class TestRateTrackParserCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_track_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_track_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__track_id__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        result = runner.invoke(app, ["rate", "track", "--email", "test@example.com", "not-a-uuid", "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for 'TRACK_ID'" in output

    def test__email__invalid(self, runner: CliRunner, clean_typer_text: TextCleaner) -> None:
        track_id = uuid.uuid4()
        result = runner.invoke(app, ["rate", "track", "--email", "notanemail", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "Invalid value for '--email'" in output


class TestRateTrackCommand:
    @pytest.fixture(autouse=True)
    def mock_rate_track_logic(self) -> Iterable[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.rate_track_logic", new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__nominal(self, mock_rate_track_logic: mock.AsyncMock, runner: CliRunner) -> None:
        track_id = uuid.uuid4()
        result = runner.invoke(app, ["rate", "track", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code == 0
        mock_rate_track_logic.assert_awaited_once()

    def test__user_not_found(
        self,
        mock_rate_track_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_track_logic.side_effect = UserNotFound()
        track_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "track", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.output)
        assert "User not found with email: test@example.com" in output

    def test__track_not_found(
        self,
        mock_rate_track_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_track_logic.side_effect = TrackNotFoundError()
        track_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "track", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert f"Track {track_id} not found." in output

    def test__rate_score_invalid(
        self,
        mock_rate_track_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_track_logic.side_effect = RateScoreInvalidException("Score out of range")
        track_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "track", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Score out of range" in output

    def test__generic_exception(
        self,
        mock_rate_track_logic: mock.AsyncMock,
        runner: CliRunner,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_rate_track_logic.side_effect = Exception("Boom")
        track_id = uuid.uuid4()

        result = runner.invoke(app, ["rate", "track", "--email", "test@example.com", str(track_id), "7"])
        assert result.exit_code != 0
        output = clean_typer_text(result.stderr)
        assert "Error: Boom" in output


@pytest.mark.usefixtures("mock_get_db", "mock_user_repository", "mock_track_repository")
class TestRateTrackLogic:
    TARGET_PATH: Final[str] = "museflow.infrastructure.entrypoints.cli.commands.rate.track"

    async def test__user_not_found(self, mock_user_repository: mock.AsyncMock) -> None:
        mock_user_repository.get_by_email.return_value = None

        with pytest.raises(UserNotFound):
            await rate_track_logic(track_id=uuid.uuid4(), score=5, email="test@example.com")

    async def test__track_not_found(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        mock_track_repository.rate.side_effect = TrackNotFoundError()

        with pytest.raises(TrackNotFoundError):
            await rate_track_logic(track_id=uuid.uuid4(), score=5, email=user.email)

    async def test__nominal(
        self,
        user: User,
        mock_user_repository: mock.AsyncMock,
        mock_track_repository: mock.AsyncMock,
    ) -> None:
        mock_user_repository.get_by_email.return_value = user
        track_id = uuid.uuid4()

        await rate_track_logic(track_id=track_id, score=7, email=user.email)

        mock_track_repository.rate.assert_awaited_once_with(user_id=user.id, track_id=track_id, score=7)
