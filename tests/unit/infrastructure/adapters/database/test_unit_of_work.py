from unittest import mock

from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork


class TestSQLUnitOfWork:
    @pytest.fixture
    def session(self) -> mock.AsyncMock:
        session = mock.AsyncMock(spec=AsyncSession)
        session.info = {}
        return session

    async def test__nested_block__raises_and_keeps_outer_block(self, session: mock.AsyncMock) -> None:
        unit_of_work = SQLUnitOfWork(session)
        commit = session.commit

        async with unit_of_work.atomic():
            with pytest.raises(RuntimeError, match="already open"):
                await unit_of_work.atomic().__aenter__()

        commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        assert session.commit is commit
        assert session.info == {}
