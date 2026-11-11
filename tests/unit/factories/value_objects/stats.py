from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.value_objects.stats import ArtistStats


class ArtistStatsFactory(DataclassFactory[ArtistStats]):
    __model__ = ArtistStats
    __set_as_default_factory_for_type__ = True

    track_count = 1
    plays_count = 1
    rated_count = 0
    rated_sum = 0
