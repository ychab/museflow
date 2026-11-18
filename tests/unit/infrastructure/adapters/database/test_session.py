import pytest

from museflow.infrastructure.adapters.database.session import create_engine_from_settings
from museflow.infrastructure.config.settings.database import database_settings


class TestCreateEngineFromSettings:
    def test__missing_database_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(database_settings, "URI", None)

        with pytest.raises(RuntimeError, match="DATABASE_ env vars"):
            create_engine_from_settings()
