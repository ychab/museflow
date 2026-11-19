from collections.abc import Iterator
from unittest import mock

from sqlalchemy.ext.asyncio import AsyncEngine

import pytest

from museflow.infrastructure.entrypoints.cli.dependencies import get_wiring
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic
from museflow.infrastructure.entrypoints.wiring import Wiring


class TestRunLogic:
    @pytest.fixture
    def mock_engine(self) -> Iterator[mock.AsyncMock]:
        engine = mock.AsyncMock(spec=AsyncEngine)
        target_path = "museflow.infrastructure.entrypoints.wiring.create_engine_from_settings"

        with mock.patch(target_path, return_value=engine):
            yield engine

    def test__wiring_open_for_the_run_only(self, mock_engine: mock.AsyncMock) -> None:
        async def main() -> Wiring:
            return get_wiring()

        assert isinstance(run_logic(main()), Wiring)
        mock_engine.dispose.assert_awaited_once()

        with pytest.raises(RuntimeError, match="No wiring open"):
            get_wiring()

    def test__error__disposes_engine(self, mock_engine: mock.AsyncMock) -> None:
        async def main() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            run_logic(main())

        mock_engine.dispose.assert_awaited_once()
