from typing import Any

from polyfactory import Use

from museflow.domain.enums import JobStatus
from museflow.infrastructure.adapters.database.models.job import JobModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class JobModelFactory(BaseModelFactory[JobModel]):
    __model__ = JobModel

    status = JobStatus.PENDING
    input: Use[[], dict[str, Any]] = Use(dict)
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
