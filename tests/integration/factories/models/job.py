import uuid
from typing import Any

from polyfactory import Use

from museflow.application.inputs.history import ImportStreamingHistoryJobInput
from museflow.domain.enums import JobStatus
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.models.job import JobModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class JobModelFactory(BaseModelFactory[JobModel]):
    __model__ = JobModel

    status = JobStatus.PENDING
    # The input of the only kind of job, a history import
    input: Use[[], dict[str, Any]] = Use(
        lambda: ImportStreamingHistoryJobInput(
            prefix=f"history/{uuid.uuid4()}",
            provider=MusicProvider.SPOTIFY,
        ).model_dump(mode="json")
    )
    result = None
    error = None
    published_at = None
    started_at = None
    finished_at = None

    @classmethod
    async def create_async(cls, **kwargs: Any) -> JobModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)
