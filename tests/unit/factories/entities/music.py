from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Track


class BaseMusicItemFactory[T: (Artist, Track)](DataclassFactory[T]):
    __is_base_factory__ = True

    name = Use(DataclassFactory.__faker__.name)

    popularity = Use(DataclassFactory.__faker__.random_int, min=0, max=100)
    top_position = Use(DataclassFactory.__faker__.random_int, min=1)


class ArtistFactory(BaseMusicItemFactory[Artist]):
    __model__ = Artist


class TrackFactory(BaseMusicItemFactory[Track]):
    __model__ = Track
