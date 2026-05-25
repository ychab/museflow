from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.music import Playlist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackSuggested


class TrackFactory(DataclassFactory[Track]):
    __model__ = Track

    name = Use(DataclassFactory.__faker__.name)
    artists = Use(lambda: [DataclassFactory.__faker__.name()])


class TrackSuggestedFactory(DataclassFactory[TrackSuggested]):
    __model__ = TrackSuggested

    artists = Use(lambda: [DataclassFactory.__faker__.name()])


class PlaylistFactory(DataclassFactory[Playlist]):
    __model__ = Playlist
