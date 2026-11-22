import logging
from unittest import mock

import pytest

from museflow.application.ports.queue import JobPublisherPort
from museflow.application.use_cases.job_publish import publish_jobs
from museflow.domain.exceptions import JobPublishError

from tests.unit.factories.entities.job import JobFactory


class TestPublishJobsUseCase:
    @pytest.fixture
    def mock_job_publisher(self) -> mock.AsyncMock:
        return mock.AsyncMock(spec=JobPublisherPort)

    async def test__publish_error__stops(
        self,
        caplog: pytest.LogCaptureFixture,
        mock_uow: mock.AsyncMock,
        mock_job_repository: mock.AsyncMock,
        mock_job_publisher: mock.AsyncMock,
    ) -> None:
        jobs = JobFactory.batch(3)
        mock_job_repository.get_unpublished.return_value = jobs
        mock_job_publisher.publish.side_effect = [None, JobPublishError("Broker down"), None]

        with caplog.at_level(logging.WARNING):
            published = await publish_jobs(10, uow=mock_uow, job_publisher=mock_job_publisher)

        # The first one only: the others wait for the next round, in their order
        assert published == 1
        assert mock_job_publisher.publish.await_count == 2
        mock_job_repository.mark_published.assert_awaited_once_with([jobs[0].id])
        assert f"Job {jobs[1].id} not published" in caplog.text

    async def test__none(
        self,
        mock_uow: mock.AsyncMock,
        mock_job_repository: mock.AsyncMock,
        mock_job_publisher: mock.AsyncMock,
    ) -> None:
        mock_job_repository.get_unpublished.return_value = []

        published = await publish_jobs(10, uow=mock_uow, job_publisher=mock_job_publisher)

        assert published == 0
        mock_job_repository.mark_published.assert_not_awaited()
