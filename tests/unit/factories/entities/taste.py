from typing import Any

from polyfactory import Use
from polyfactory.factories import DataclassFactory
from polyfactory.factories import TypedDictFactory

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileData


class TasteProfileDataFactory(TypedDictFactory[TasteProfileData]):
    __model__ = TasteProfileData


class TasteProfileFactory(DataclassFactory[TasteProfile]):
    __model__ = TasteProfile

    profile = Use(TasteProfileDataFactory.build)
    profiler_metadata: dict[str, Any] = {}
