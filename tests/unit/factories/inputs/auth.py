from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from museflow.application.inputs.auth import OAuthProviderUserTokenCreateInput
from museflow.application.inputs.auth import OAuthProviderUserTokenUpdateInput


class OAuthProviderUserTokenCreateInputFactory(ModelFactory[OAuthProviderUserTokenCreateInput]):
    __model__ = OAuthProviderUserTokenCreateInput

    token_type = "bearer"
    # Never empty: a max length without a min lets polyfactory pick 0, and an empty token type or token makes an
    # illegal Authorization header.
    token_access = Use(ModelFactory.__faker__.sha256)
    token_refresh = Use(ModelFactory.__faker__.sha256)


class OAuthProviderUserTokenUpdateInputFactory(ModelFactory[OAuthProviderUserTokenUpdateInput]):
    __model__ = OAuthProviderUserTokenUpdateInput
    # Force all optional fields to have real values so bulk-update tests exercise every field.
    __allow_none_optionals__ = False

    # Never empty, as in OAuthProviderUserTokenCreateInputFactory; the type differs from the stored "bearer", so an
    # update test proves the field is written.
    token_type = Use(ModelFactory.__faker__.pystr)
    token_access = Use(ModelFactory.__faker__.sha256)
    token_refresh = Use(ModelFactory.__faker__.sha256)
