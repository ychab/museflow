from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.value_objects.taste import ArtistSuggested
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy


class ArtistSuggestedFactory(DataclassFactory[ArtistSuggested]):
    __model__ = ArtistSuggested

    name = Use(DataclassFactory.__faker__.name)


class DiscoveryArtistStrategyFactory(DataclassFactory[DiscoveryArtistStrategy]):
    __model__ = DiscoveryArtistStrategy

    artists = Use(lambda: ArtistSuggestedFactory.batch(1))
