from unittest import mock

from sqlalchemy.ext.asyncio import AsyncSession

import pytest

from museflow.infrastructure.adapters.database.unit_of_work import SQLUnitOfWork


class TestSQLUnitOfWork:
    @pytest.fixture
    def session(self) -> mock.AsyncMock:
        return mock.AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def unit_of_work(self, session: mock.AsyncMock) -> SQLUnitOfWork:
        return SQLUnitOfWork(mock.Mock(return_value=session))

    async def test__nested_block__raises_and_keeps_outer_block(
        self,
        unit_of_work: SQLUnitOfWork,
        session: mock.AsyncMock,
    ) -> None:
        async with unit_of_work:
            with pytest.raises(RuntimeError, match="already open"):
                await unit_of_work.__aenter__()

        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
        session.close.assert_awaited_once()

    async def test__commit_fails__closes_session(self, unit_of_work: SQLUnitOfWork, session: mock.AsyncMock) -> None:
        session.commit.side_effect = RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            async with unit_of_work:
                pass

        session.close.assert_awaited_once()
        assert unit_of_work.session is None

    async def test__rollback__outside_block__raises(self, unit_of_work: SQLUnitOfWork) -> None:
        with pytest.raises(RuntimeError, match="No unit of work block is open"):
            await unit_of_work.rollback()
