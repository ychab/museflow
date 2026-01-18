from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from spotifagent.domain.entities.music import TopArtist
from spotifagent.domain.entities.music import TopTrack


class BaseTopItemFactory[T: (TopArtist, TopTrack)](ModelFactory[T]):
    __is_base_factory__ = True

    name = Use(ModelFactory.__faker__.name)


class TopArtistFactory(BaseTopItemFactory[TopArtist]):
    __model__ = TopArtist


class TopTrackFactory(BaseTopItemFactory[TopTrack]):
    __model__ = TopTrack
