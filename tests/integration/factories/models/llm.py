from datetime import datetime
from typing import Any

from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class LLMUsageModelFactory(BaseModelFactory[LLMUsageModel]):
    __model__ = LLMUsageModel

    profile_id = None
    playlist_id = None

    @classmethod
    async def create_async(cls, **kwargs: Any) -> LLMUsageModel:
        # Not an init field: the database sets it, so a test backdates the row after the insert.
        created_at: datetime | None = kwargs.pop("created_at", None)

        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        usage_db = await super().create_async(**kwargs)

        if created_at is not None:
            usage_db.created_at = created_at
            # The session does not autoflush: without it, a query right after would not see the new date.
            await cls.__async_session__.flush()  # type: ignore[union-attr]

        return usage_db
