from museflow.application.inputs.auth import OAuthProviderUserTokenCreateInput
from museflow.application.inputs.auth import OAuthProviderUserTokenUpdateInput
from museflow.domain.value_objects.auth import OAuthProviderTokenPayload


def to_auth_token_create_input(
    token_payload: OAuthProviderTokenPayload,
) -> OAuthProviderUserTokenCreateInput:
    return OAuthProviderUserTokenCreateInput(
        token_type=token_payload.token_type,
        token_access=token_payload.access_token,
        token_refresh=token_payload.refresh_token,
        token_expires_at=token_payload.expires_at,
    )


def to_auth_token_update_input(
    token_payload: OAuthProviderTokenPayload,
) -> OAuthProviderUserTokenUpdateInput:
    return OAuthProviderUserTokenUpdateInput(
        token_type=token_payload.token_type,
        token_access=token_payload.access_token,
        token_refresh=token_payload.refresh_token,
        token_expires_at=token_payload.expires_at,
    )
