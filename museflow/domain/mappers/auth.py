from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.value_objects.auth import OAuthProviderTokenPayload


def to_token_payload(auth_token: OAuthProviderUserToken) -> OAuthProviderTokenPayload:
    return OAuthProviderTokenPayload(
        token_type=auth_token.token_type,
        access_token=auth_token.token_access,
        refresh_token=auth_token.token_refresh,
        expires_at=auth_token.token_expires_at,
    )
