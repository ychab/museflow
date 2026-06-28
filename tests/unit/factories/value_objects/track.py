from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.value_objects.track import TrackEnrichment


class TrackEnrichmentFactory(DataclassFactory[TrackEnrichment]):
    __model__ = TrackEnrichment
    __set_as_default_factory_for_type__ = True

    genres = Use(lambda: ["indie folk", "dream pop"])
    moods = Use(lambda: ["chill"])
