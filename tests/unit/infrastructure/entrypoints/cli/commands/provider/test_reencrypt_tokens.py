from collections.abc import Iterable
from unittest import mock

import pytest
from typer.testing import CliRunner

from museflow.infrastructure.entrypoints.cli.main import app

from tests.unit.infrastructure.entrypoints.cli.conftest import TextCleaner


class TestProviderReencryptTokensParserCommand:
    @pytest.fixture(autouse=True)
    def mock_provider_reencrypt_tokens_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.provider.reencrypt_tokens.provider_reencrypt_tokens_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            patched.return_value = 0
            yield patched

    def test__nominal(self, mock_provider_reencrypt_tokens_logic: mock.AsyncMock, runner: CliRunner) -> None:
        result = runner.invoke(app, ["provider", "reencrypt-tokens"])

        assert result.exit_code == 0
        mock_provider_reencrypt_tokens_logic.assert_awaited_once_with()


class TestProviderReencryptTokensCommand:
    @pytest.fixture(autouse=True)
    def mock_provider_reencrypt_tokens_logic(self) -> Iterable[mock.AsyncMock]:
        target_path = "museflow.infrastructure.entrypoints.cli.commands.provider.reencrypt_tokens.provider_reencrypt_tokens_logic"
        with mock.patch(target_path, new_callable=mock.AsyncMock) as patched:
            yield patched

    def test__output__nominal(
        self,
        runner: CliRunner,
        mock_provider_reencrypt_tokens_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_provider_reencrypt_tokens_logic.return_value = 3

        result = runner.invoke(app, ["provider", "reencrypt-tokens"])

        assert result.exit_code == 0
        assert "Encrypted 3 token(s) again with the current key." in clean_typer_text(result.stdout)

    def test__output__exceptions(
        self,
        runner: CliRunner,
        mock_provider_reencrypt_tokens_logic: mock.AsyncMock,
        clean_typer_text: TextCleaner,
    ) -> None:
        mock_provider_reencrypt_tokens_logic.side_effect = Exception("Boom")

        result = runner.invoke(app, ["provider", "reencrypt-tokens"])

        assert result.exit_code != 0
        assert "Error: Boom" in clean_typer_text(result.stderr)
