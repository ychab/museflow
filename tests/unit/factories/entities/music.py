from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.music import Album
from museflow.domain.entities.music import Playlist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackArtist
from museflow.domain.entities.music import TrackSuggested


class AlbumFactory(DataclassFactory[Album]):
    __model__ = Album
    __set_as_default_factory_for_type__ = True


class TrackArtistFactory(DataclassFactory[TrackArtist]):
    __model__ = TrackArtist
    __set_as_default_factory_for_type__ = True


class TrackFactory(DataclassFactory[Track]):
    __model__ = Track

    name = Use(DataclassFactory.__faker__.name)


class TrackSuggestedFactory(DataclassFactory[TrackSuggested]):
    __model__ = TrackSuggested


class PlaylistFactory(DataclassFactory[Playlist]):
    __model__ = Playlist
