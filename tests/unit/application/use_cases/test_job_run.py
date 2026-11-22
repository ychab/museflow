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
