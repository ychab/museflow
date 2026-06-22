import uuid

from polyfactory import Use
from polyfactory.decorators import post_generated
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.playlist import Playlist
from museflow.domain.types import PlaylistType

from tests.unit.factories.entities.track import TrackFactory


class PlaylistFactory(DataclassFactory[Playlist]):
    __model__ = Playlist
    __set_as_default_factory_for_type__ = True
    __use_defaults__ = True

    name = Use(DataclassFactory.__faker__.sentence)
    type = PlaylistType.DISCOVERY
    tracks = Use(lambda: TrackFactory.batch(3))

    @post_generated
    @classmethod
    def profile_id(cls, type: PlaylistType) -> uuid.UUID | None:
        return uuid.uuid4() if type == PlaylistType.DISCOVERY else None

    @post_generated
    @classmethod
    def reasoning(cls, type: PlaylistType) -> str | None:
        return cls.__faker__.paragraph() if type == PlaylistType.DISCOVERY else None

    @post_generated
    @classmethod
    def genre(cls, type: PlaylistType) -> str | None:
        return cls.__faker__.word() if type == PlaylistType.DISCOVERY else None

    @post_generated
    @classmethod
    def mood(cls, type: PlaylistType) -> str | None:
        return cls.__faker__.word() if type == PlaylistType.DISCOVERY else None

    @post_generated
    @classmethod
    def custom_instructions(cls, type: PlaylistType) -> str | None:
        return cls.__faker__.sentence() if type == PlaylistType.DISCOVERY else None
