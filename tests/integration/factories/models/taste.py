from typing import Any

from polyfactory import Use
from polyfactory.factories import TypedDictFactory

from museflow.domain.entities.taste import TasteProfileData
from museflow.infrastructure.adapters.database.models.taste import TasteProfileModel

from tests.integration.factories.models.base import BaseModelFactory
from tests.integration.factories.models.user import UserModelFactory


class TasteProfileDataFactory(TypedDictFactory[TasteProfileData]):
    __model__ = TasteProfileData


class TasteProfileModelFactory(BaseModelFactory[TasteProfileModel]):
    __model__ = TasteProfileModel

    profile = Use(TasteProfileDataFactory.build)

    @classmethod
    async def create_async(cls, **kwargs: Any) -> TasteProfileModel:
        if "user_id" not in kwargs:
            user = await UserModelFactory.create_async()
            kwargs["user_id"] = user.id

        return await super().create_async(**kwargs)
