import uuid
from unittest import mock

import pytest

from museflow.application.use_cases.job_get import get_job
from museflow.domain.entities.user import User
from museflow.domain.exceptions import JobNotFoundError


class TestGetJobUseCase:
    async def test__not_found(self, user: User, mock_uow: mock.AsyncMock, mock_job_repository: mock.AsyncMock) -> None:
        mock_job_repository.get.return_value = None

        with pytest.raises(JobNotFoundError):
            await get_job(user=user, job_id=uuid.uuid4(), uow=mock_uow)
