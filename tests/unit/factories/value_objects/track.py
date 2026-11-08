from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.enums import GenreTag
from museflow.domain.value_objects.track import TrackEnrichment
from museflow.domain.value_objects.track import TrackPlay


class TrackEnrichmentFactory(DataclassFactory[TrackEnrichment]):
    __model__ = TrackEnrichment
    __set_as_default_factory_for_type__ = True

    genres = Use(lambda: [GenreTag.FOLK, GenreTag.INDIE_FOLK])
    moods = Use(lambda: ["chill"])
    locales = None


class TrackPlayFactory(DataclassFactory[TrackPlay]):
    __model__ = TrackPlay
    __set_as_default_factory_for_type__ = True
