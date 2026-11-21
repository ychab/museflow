from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.application.outputs.stats import ArtistStats
from museflow.application.outputs.stats import TagStats


class ArtistStatsFactory(DataclassFactory[ArtistStats]):
    __model__ = ArtistStats
    __set_as_default_factory_for_type__ = True

    track_count = 1
    plays_count = 1
    rated_count = 0
    rated_sum = 0


class TagStatsFactory(DataclassFactory[TagStats]):
    __model__ = TagStats
    __set_as_default_factory_for_type__ = True

    track_count = 1
    plays_count = 1
    rated_count = 0
    rated_sum = 0
