from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from museflow.domain.entities.music import Artist
from museflow.domain.entities.music import Track


class BaseMusicItemFactory[T: (Artist, Track)](ModelFactory[T]):
    __is_base_factory__ = True

    name = Use(ModelFactory.__faker__.name)

    popularity = Use(ModelFactory.__faker__.random_int, min=0, max=100)
    top_position = Use(ModelFactory.__faker__.random_int, min=1)


class ArtistFactory(BaseMusicItemFactory[Artist]):
    __model__ = Artist


class TrackFactory(BaseMusicItemFactory[Track]):
    __model__ = Track
