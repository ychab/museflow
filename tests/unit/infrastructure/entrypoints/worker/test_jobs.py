import uuid
from collections.abc import Coroutine
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from celery import Task

from museflow.infrastructure.entrypoints.worker.jobs import run_job

from tests.unit.factories.entities.job import JobFactory

TARGET_PATH = "museflow.infrastructure.entrypoints.worker.jobs"


class TestRunJob:
    @pytest.fixture
    def mock_use_case(self) -> Iterator[mock.AsyncMock]:
        with mock.patch(f"{TARGET_PATH}.RunJobUseCase") as patched:
            use_case = patched.return_value
            use_case.start = mock.AsyncMock(return_value=JobFactory.build())
            use_case.finish = mock.AsyncMock()
            use_case.fail = mock.AsyncMock()
            yield use_case

    @pytest.fixture
    def mock_get_wiring(self) -> Iterator[mock.Mock]:
        with mock.patch(f"{TARGET_PATH}.get_wiring") as patched:
            yield patched

    @pytest.fixture
    def mock_run_task(self) -> Iterator[mock.Mock]:
        with mock.patch(f"{TARGET_PATH}.run_task") as patched:
            yield patched

    @pytest.fixture
    def task(self, request: pytest.FixtureRequest) -> mock.Mock:
        """A bound task on its try `request.param` (0: the first), out of 5."""
        task = mock.Mock(spec=Task)
        task.max_retries = 5
        task.request.retries = getattr(request, "param", 0)
        task.request.delivery_info = None
        return task

    async def _run(self, mock_run_task: mock.Mock, task: mock.Mock, work: Any) -> None:
        run_job(task, str(uuid.uuid4()), str(uuid.uuid4()), work)
        coroutine: Coroutine[Any, Any, None] = mock_run_task.call_args.args[0]
        await coroutine

    @pytest.mark.parametrize("task", [1], indirect=True)
    async def test__retried__resumed(
        self,
        task: mock.Mock,
        mock_use_case: mock.AsyncMock,
        mock_get_wiring: mock.Mock,
        mock_run_task: mock.Mock,
    ) -> None:
        await self._run(mock_run_task, task, mock.AsyncMock(return_value=None))

        mock_use_case.start.assert_awaited_once_with(resumed=True)

    async def test__transient_error__retried(
        self,
        task: mock.Mock,
        mock_use_case: mock.AsyncMock,
        mock_get_wiring: mock.Mock,
        mock_run_task: mock.Mock,
    ) -> None:
        with pytest.raises(ConnectionError):
            await self._run(mock_run_task, task, mock.AsyncMock(side_effect=ConnectionError))

        # Celery retries it: the job stays running
        mock_use_case.fail.assert_not_awaited()

    @pytest.mark.parametrize("task", [5], indirect=True)
    async def test__transient_error__last_try__failed(
        self,
        task: mock.Mock,
        mock_use_case: mock.AsyncMock,
        mock_get_wiring: mock.Mock,
        mock_run_task: mock.Mock,
    ) -> None:
        with pytest.raises(ConnectionError):
            await self._run(mock_run_task, task, mock.AsyncMock(side_effect=ConnectionError))

        mock_use_case.fail.assert_awaited_once_with("ConnectionError")
