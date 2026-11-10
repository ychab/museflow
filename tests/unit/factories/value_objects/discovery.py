from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.value_objects.taste import ArtistSuggested
from museflow.domain.value_objects.taste import DiscoveryArtistStrategy
from museflow.domain.value_objects.taste import DiscoveryTasteStrategy
from museflow.domain.value_objects.taste import TrackPicked

from tests.unit.factories.entities.track import TrackFactory


class DiscoveryTasteStrategyFactory(DataclassFactory[DiscoveryTasteStrategy]):
    __model__ = DiscoveryTasteStrategy


class ArtistSuggestedFactory(DataclassFactory[ArtistSuggested]):
    __model__ = ArtistSuggested

    name = Use(DataclassFactory.__faker__.name)


class DiscoveryArtistStrategyFactory(DataclassFactory[DiscoveryArtistStrategy]):
    __model__ = DiscoveryArtistStrategy

    artists = Use(lambda: ArtistSuggestedFactory.batch(1))


class TrackPickedFactory(DataclassFactory[TrackPicked]):
    __model__ = TrackPicked

    track = Use(TrackFactory.build)
