import uuid

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.schemas.auth import OAuthProviderTokenPayload
from museflow.domain.schemas.auth import OAuthProviderUserTokenCreate
from museflow.domain.schemas.auth import OAuthProviderUserTokenUpdate
from museflow.domain.types import MusicProvider


def auth_token_from_token_payload(
    auth_token_id: int,
    user_id: uuid.UUID,
    provider: MusicProvider,
    token_payload: OAuthProviderTokenPayload,
) -> OAuthProviderUserToken:
    return OAuthProviderUserToken(
        id=auth_token_id,
        user_id=user_id,
        provider=provider,
        token_type=token_payload.token_type,
        token_access=token_payload.access_token,
        token_refresh=token_payload.refresh_token,
        token_expires_at=token_payload.expires_at,
    )


def auth_token_to_token_payload(auth_token: OAuthProviderUserToken) -> OAuthProviderTokenPayload:
    return OAuthProviderTokenPayload(
        token_type=auth_token.token_type,
        access_token=auth_token.token_access,
        refresh_token=auth_token.token_refresh,
        expires_at=auth_token.token_expires_at,
    )


def auth_token_create_from_token_payload(token_payload: OAuthProviderTokenPayload) -> OAuthProviderUserTokenCreate:
    return OAuthProviderUserTokenCreate(
        token_type=token_payload.token_type,
        token_access=token_payload.access_token,
        token_refresh=token_payload.refresh_token,
        token_expires_at=token_payload.expires_at,
    )


def auth_token_update_from_token_payload(token_payload: OAuthProviderTokenPayload) -> OAuthProviderUserTokenUpdate:
    return OAuthProviderUserTokenUpdate(
        token_type=token_payload.token_type,
        token_access=token_payload.access_token,
        token_refresh=token_payload.refresh_token,
        token_expires_at=token_payload.expires_at,
    )
