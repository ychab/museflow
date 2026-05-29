from polyfactory.factories import DataclassFactory

from museflow.domain.entities.blacklist import BlacklistedArtist
from museflow.domain.entities.blacklist import BlacklistedTrack
from museflow.domain.value_objects.blacklist import UserBlacklist


class BlacklistedArtistFactory(DataclassFactory[BlacklistedArtist]):
    __model__ = BlacklistedArtist
    __set_as_default_factory_for_type__ = True
    __use_defaults__ = True

    artist_name = DataclassFactory.__faker__.name


class BlacklistedTrackFactory(DataclassFactory[BlacklistedTrack]):
    __model__ = BlacklistedTrack
    __set_as_default_factory_for_type__ = True
    __use_defaults__ = True

    name = DataclassFactory.__faker__.sentence
    artist_name = DataclassFactory.__faker__.name


class UserBlacklistFactory(DataclassFactory[UserBlacklist]):
    __model__ = UserBlacklist
