from collections.abc import Iterator
from unittest import mock

from sqlalchemy.ext.asyncio import AsyncEngine

import pytest

from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork
from museflow.infrastructure.entrypoints.cli.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.cli.dependencies import run_logic


class TestRunWithDatabase:
    @pytest.fixture
    def mock_engine(self) -> Iterator[mock.AsyncMock]:
        engine = mock.AsyncMock(spec=AsyncEngine)
        target_path = "museflow.infrastructure.entrypoints.cli.dependencies.create_engine_from_settings"
        with mock.patch(target_path, return_value=engine):
            yield engine

    def test__database_open_for_the_run_only(self, mock_engine: mock.AsyncMock) -> None:
        async def main() -> UnitOfWorkPort:
            return get_unit_of_work()

        assert isinstance(run_logic(main()), SQLUnitOfWork)
        mock_engine.dispose.assert_awaited_once()

        with pytest.raises(RuntimeError, match="No database open"):
            get_unit_of_work()

    def test__error__disposes_engine(self, mock_engine: mock.AsyncMock) -> None:
        async def main() -> None:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            run_logic(main())

        mock_engine.dispose.assert_awaited_once()
