from pydantic import ValidationError

import pytest

from museflow.infrastructure.config.settings.app import AppSettings


class TestAppSettings:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param("", None, id="empty"),
            pytest.param("user@example.com", "user@example.com", id="valid"),
        ],
    )
    def test__cli_default_email(self, monkeypatch: pytest.MonkeyPatch, value: str, expected: str | None) -> None:
        monkeypatch.setenv("MUSEFLOW_CLI_DEFAULT_EMAIL", value)

        settings = AppSettings(_env_file=None)

        assert settings.CLI_DEFAULT_EMAIL == expected

    def test__cli_default_email__invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MUSEFLOW_CLI_DEFAULT_EMAIL", "not-an-email")

        with pytest.raises(ValidationError, match="An email address must have an @-sign"):
            AppSettings(_env_file=None)
