from polyfactory.factories.pydantic_factory import ModelFactory

from museflow.application.inputs.auth import OAuthProviderUserTokenCreateInput
from museflow.application.inputs.auth import OAuthProviderUserTokenUpdateInput


class OAuthProviderUserTokenCreateInputFactory(ModelFactory[OAuthProviderUserTokenCreateInput]):
    __model__ = OAuthProviderUserTokenCreateInput


class OAuthProviderUserTokenUpdateInputFactory(ModelFactory[OAuthProviderUserTokenUpdateInput]):
    __model__ = OAuthProviderUserTokenUpdateInput
    __allow_none_optionals__ = False
