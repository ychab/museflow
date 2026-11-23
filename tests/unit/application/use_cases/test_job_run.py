import logging
import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.job_run import RunJobUseCase


class TestRunJobUseCase:
    async def test__start__not_started(
        self,
        caplog: pytest.LogCaptureFixture,
        mock_uow: mock.AsyncMock,
        mock_job_repository: mock.AsyncMock,
    ) -> None:
        job_id = uuid.uuid4()
        mock_job_repository.start.return_value = None
        use_case = RunJobUseCase(user_id=uuid.uuid4(), job_id=job_id, uow=mock_uow)

        with caplog.at_level(logging.INFO):
            job = await use_case.start(resumed=False)

        assert job is None
        assert f"Job {job_id} not started" in caplog.text

    async def test__finish__not_running(
        self,
        caplog: pytest.LogCaptureFixture,
        mock_uow: mock.AsyncMock,
        mock_job_repository: mock.AsyncMock,
    ) -> None:
        job_id = uuid.uuid4()
        mock_job_repository.finish.return_value = False
        use_case = RunJobUseCase(user_id=uuid.uuid4(), job_id=job_id, uow=mock_uow)

        with caplog.at_level(logging.INFO):
            await use_case.finish(None)

        assert f"Job {job_id} not finished: no longer running" in caplog.text
        assert f"Job {job_id} done" not in caplog.text

    async def test__fail__not_running(
        self,
        caplog: pytest.LogCaptureFixture,
        mock_uow: mock.AsyncMock,
        mock_job_repository: mock.AsyncMock,
    ) -> None:
        job_id = uuid.uuid4()
        mock_job_repository.fail.return_value = False
        use_case = RunJobUseCase(user_id=uuid.uuid4(), job_id=job_id, uow=mock_uow)

        with caplog.at_level(logging.WARNING):
            await use_case.fail("ValueError")

        assert f"Job {job_id} not failed: no longer running" in caplog.text
