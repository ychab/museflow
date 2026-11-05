from typing import Any

from polyfactory import Use
from polyfactory.factories import TypedDictFactory

from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.taste import TasteProfileStatus
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TasteProfileDataFactory(TypedDictFactory[TasteProfileData]):
    __model__ = TasteProfileData


class TasteProfileModelFactory(BaseModelFactory[TasteProfileModel]):
    __model__ = TasteProfileModel

    # Never empty: String(n) gives polyfactory no min length, and record_llm_usage reads an empty name as no profile.
    name = Use(BaseModelFactory.__faker__.sha256)
    profile = Use(TasteProfileDataFactory.build)
    status = TasteProfileStatus.FINISHED

    @classmethod
    async def create_async(cls, **kwargs: Any) -> TasteProfileModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)
