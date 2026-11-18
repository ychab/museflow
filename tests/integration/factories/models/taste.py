from typing import Any

from polyfactory import Use
from polyfactory.factories import TypedDictFactory

from museflow.domain.enums import TasteProfileStatus
from museflow.domain.value_objects.taste import TasteProfileData
from museflow.infrastructure.adapters.database.models.taste import TasteProfileBuildModel
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TasteProfileDataFactory(TypedDictFactory[TasteProfileData]):
    __model__ = TasteProfileData


class TasteProfileModelFactory(BaseModelFactory[TasteProfileModel]):
    __model__ = TasteProfileModel

    # Never empty: String(n) gives polyfactory no min length, and LLMUsageService.record reads an empty name as no profile.
    name = Use(BaseModelFactory.__faker__.sha256)
    profile = Use(TasteProfileDataFactory.build)
    status = TasteProfileStatus.FINISHED

    @classmethod
    async def create_async(cls, **kwargs: Any) -> TasteProfileModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)


class TasteProfileBuildModelFactory(BaseModelFactory[TasteProfileBuildModel]):
    __model__ = TasteProfileBuildModel

    name = Use(BaseModelFactory.__faker__.sha256)

    @classmethod
    async def create_async(cls, **kwargs: Any) -> TasteProfileBuildModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)
