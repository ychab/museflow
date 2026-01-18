from pydantic import ValidationError

import pytest

from spotifagent.infrastructure.config.settings.database import DatabaseSettings


class TestDatabaseSettings:
    def test_uri_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_HOST", raising=False)
        monkeypatch.delenv("DATABASE_PORT", raising=False)
        monkeypatch.delenv("DATABASE_USER", raising=False)
        monkeypatch.delenv("DATABASE_PASSWORD", raising=False)
        monkeypatch.delenv("DATABASE_PATH", raising=False)

        monkeypatch.setenv("DATABASE_URI", "postgresql+asyncpg://user:pass@localhost:5432/testdb")
        settings = DatabaseSettings(_env_file=None)
        assert str(settings.URI) == "postgresql+asyncpg://user:pass@localhost:5432/testdb"

    def test_components_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URI", raising=False)

        monkeypatch.setenv("DATABASE_HOST", "localhost")
        monkeypatch.setenv("DATABASE_PORT", "5432")
        monkeypatch.setenv("DATABASE_USER", "testuser")
        monkeypatch.setenv("DATABASE_PASSWORD", "testpass")
        monkeypatch.setenv("DATABASE_PATH", "testdb")

        settings = DatabaseSettings(_env_file=None)
        assert str(settings.URI) == "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"

    def test_uri_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URI", "postgresql+asyncpg://uri_user:pass@uri-host:5432/uri_db")
        monkeypatch.setenv("DATABASE_HOST", "component_host")
        monkeypatch.setenv("DATABASE_USER", "component_user")

        settings = DatabaseSettings(_env_file=None)
        assert str(settings.URI) == "postgresql+asyncpg://uri_user:pass@uri-host:5432/uri_db"

    def test_missing_components_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URI", raising=False)
        monkeypatch.delenv("DATABASE_USER", raising=False)
        monkeypatch.delenv("DATABASE_PASSWORD", raising=False)
        monkeypatch.delenv("DATABASE_PATH", raising=False)

        monkeypatch.setenv("DATABASE_HOST", "localhost")
        monkeypatch.setenv("DATABASE_PORT", "5432")

        with pytest.raises(ValidationError) as exc_info:
            # Disable .env file loading for this test
            DatabaseSettings(_env_file=None)

        error_message = str(exc_info.value)
        assert "DATABASE_URI not provided." in error_message
        assert "USER" in error_message
        assert "PASSWORD" in error_message
        assert "PATH" in error_message
