from typing import Any

from polyfactory import Use
from polyfactory.factories import DataclassFactory
from polyfactory.factories import TypedDictFactory

from museflow.domain.entities.taste import TasteEra
from museflow.domain.entities.taste import TasteProfile
from museflow.domain.entities.taste import TasteProfileData
from museflow.domain.entities.taste import TechnicalFingerprint


class TechnicalFingerprintFactory(TypedDictFactory[TechnicalFingerprint]):
    __model__ = TechnicalFingerprint
    __set_as_default_factory_for_type__ = True


class TasteEraFactory(TypedDictFactory[TasteEra]):
    __model__ = TasteEra
    __set_as_default_factory_for_type__ = True

    # Use() is intentional here: auto-resolution alone is insufficient for nested TypedDicts.
    technical_fingerprint = Use(TechnicalFingerprintFactory.build)


class TasteProfileDataFactory(TypedDictFactory[TasteProfileData]):
    __model__ = TasteProfileData
    __set_as_default_factory_for_type__ = True


class TasteProfileFactory(DataclassFactory[TasteProfile]):
    __model__ = TasteProfile

    profiler_metadata: dict[str, Any] = {}
