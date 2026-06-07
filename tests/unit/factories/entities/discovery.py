from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.discovery import DiscoveryPlaylist


class DiscoveryPlaylistFactory(DataclassFactory[DiscoveryPlaylist]):
    __model__ = DiscoveryPlaylist
    __set_as_default_factory_for_type__ = True
    __use_defaults__ = True

    name = DataclassFactory.__faker__.sentence
    reasoning = DataclassFactory.__faker__.paragraph
    genre = None
    mood = None
    custom_instructions = None

    tracks: list = []
