from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.music import Album
from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Playlist
from museflow.domain.entities.music import Track
from museflow.domain.entities.music import TrackArtist
from museflow.domain.entities.music import TrackSuggested


class BaseMusicItemFactory[T: (Artist, Track)](DataclassFactory[T]):
    __is_base_factory__ = True

    name = Use(DataclassFactory.__faker__.name)

    popularity = Use(DataclassFactory.__faker__.random_int, min=0, max=100)
    top_position = Use(DataclassFactory.__faker__.random_int, min=1)


class ArtistFactory(BaseMusicItemFactory[Artist]):
    __model__ = Artist


class AlbumFactory(DataclassFactory[Album]):
    __model__ = Album
    __set_as_default_factory_for_type__ = True


class TrackArtistFactory(DataclassFactory[TrackArtist]):
    __model__ = TrackArtist
    __set_as_default_factory_for_type__ = True


class TrackFactory(BaseMusicItemFactory[Track]):
    __model__ = Track


class TrackSuggestedFactory(DataclassFactory[TrackSuggested]):
    __model__ = TrackSuggested


class PlaylistFactory(DataclassFactory[Playlist]):
    __model__ = Playlist
