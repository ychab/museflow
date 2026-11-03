import uuid
from datetime import datetime
from typing import Any

from polyfactory import Use

from museflow.infrastructure.adapters.database.models.llm import LLMUsageModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class LLMUsageModelFactory(BaseModelFactory[LLMUsageModel]):
    __model__ = LLMUsageModel

    run_id = Use(uuid.uuid4)
    profile_id = None
    playlist_id = None

    # Bounded to fit the columns: 4-byte integers and Numeric(12, 6).
    step = Use(BaseModelFactory.__faker__.word)
    model = Use(BaseModelFactory.__faker__.word)
    calls = Use(BaseModelFactory.__faker__.pyint, min_value=1, max_value=10)
    prompt_tokens = Use(BaseModelFactory.__faker__.pyint, max_value=100_000)
    completion_tokens = Use(BaseModelFactory.__faker__.pyint, max_value=100_000)
    reasoning_tokens = Use(BaseModelFactory.__faker__.pyint, max_value=100_000)
    cost = Use(BaseModelFactory.__faker__.pydecimal, left_digits=1, right_digits=6, positive=True)

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
            await cls.__async_session__.flush()  # type: ignore[union-attr]

        return usage_db
