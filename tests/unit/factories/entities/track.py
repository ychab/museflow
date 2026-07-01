from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from museflow.domain.entities.track import ProviderLink
from museflow.domain.entities.track import Track
from museflow.domain.entities.track import TrackSuggested
from museflow.domain.enums import MusicProvider
from museflow.domain.enums import TrackSource


class ProviderLinkFactory(DataclassFactory[ProviderLink]):
    __model__ = ProviderLink
    __set_as_default_factory_for_type__ = True

    provider = MusicProvider.SPOTIFY
    provider_id = Use(DataclassFactory.__faker__.uuid4)


class TrackFactory(DataclassFactory[Track]):
    __model__ = Track

    name = Use(DataclassFactory.__faker__.name)
    artists = Use(lambda: [DataclassFactory.__faker__.name()])
    fingerprint = ""
    provider_links = Use(lambda: [ProviderLinkFactory.build()])

    source = TrackSource.HISTORY
    score = None
    score_skipped = False
    locale = None


class TrackSuggestedFactory(DataclassFactory[TrackSuggested]):
    __model__ = TrackSuggested

    artists = Use(lambda: [DataclassFactory.__faker__.name()])
