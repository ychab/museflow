from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.music import Playlist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackSuggested
from museflow.domain.types import TrackSource


class TrackFactory(DataclassFactory[Track]):
    __model__ = Track

    name = Use(DataclassFactory.__faker__.name)
    artists = Use(lambda: [DataclassFactory.__faker__.name()])
    fingerprint = ""

    source = TrackSource.HISTORY
    score = None


class TrackSuggestedFactory(DataclassFactory[TrackSuggested]):
    __model__ = TrackSuggested

    artists = Use(lambda: [DataclassFactory.__faker__.name()])


class PlaylistFactory(DataclassFactory[Playlist]):
    __model__ = Playlist
