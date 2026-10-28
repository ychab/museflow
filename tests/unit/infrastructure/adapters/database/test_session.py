import importlib

import pytest

from museflow.infrastructure.adapters.database import session as session_module
from museflow.infrastructure.config.settings.database import database_settings


class TestSessionModule:
    @pytest.fixture
    def unset_database_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(database_settings, "URI", None)

    @pytest.mark.usefixtures("unset_database_uri")
    def test__missing_database_uri(self) -> None:
        with pytest.raises(RuntimeError, match="DATABASE_ env vars"):
            importlib.reload(session_module)
