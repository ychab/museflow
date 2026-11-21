from pydantic import ValidationError

import pytest

from museflow.infrastructure.config.settings.broker import BrokerSettings


class TestBrokerSettings:
    def test__url_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for component in ("HOST", "PORT", "USER", "PASSWORD"):
            monkeypatch.delenv(f"BROKER_{component}", raising=False)
        monkeypatch.setenv("BROKER_URL", "amqp://user:pass@rabbitmq:5672//")

        settings = BrokerSettings(_env_file=None)
        assert settings.URL is not None
        assert settings.URL.get_secret_value() == "amqp://user:pass@rabbitmq:5672//"

    def test__components_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BROKER_URL", raising=False)
        monkeypatch.setenv("BROKER_HOST", "localhost")
        monkeypatch.setenv("BROKER_PORT", "5673")
        monkeypatch.setenv("BROKER_USER", "testuser")
        monkeypatch.setenv("BROKER_PASSWORD", "test@pass")

        settings = BrokerSettings(_env_file=None)
        assert settings.URL is not None
        assert settings.URL.get_secret_value() == "amqp://testuser:test%40pass@localhost:5673//"

    def test__url_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BROKER_URL", "amqp://url_user:pass@url-host:5672//")
        monkeypatch.setenv("BROKER_HOST", "component_host")

        settings = BrokerSettings(_env_file=None)
        assert settings.URL is not None
        assert settings.URL.get_secret_value() == "amqp://url_user:pass@url-host:5672//"

    def test__missing_components_raises_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BROKER_URL", raising=False)
        monkeypatch.delenv("BROKER_USER", raising=False)
        monkeypatch.delenv("BROKER_PASSWORD", raising=False)
        monkeypatch.setenv("BROKER_HOST", "localhost")
        monkeypatch.setenv("BROKER_PORT", "5672")

        with pytest.raises(ValidationError, match="BROKER_URL not provided.*USER, PASSWORD"):
            BrokerSettings(_env_file=None)
