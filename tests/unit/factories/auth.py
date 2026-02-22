from polyfactory.factories.pydantic_factory import ModelFactory

from spotifagent.domain.entities.auth import OAuthProviderState


class OAuthProviderStateFactory(ModelFactory[OAuthProviderState]):
    __model__ = OAuthProviderState
