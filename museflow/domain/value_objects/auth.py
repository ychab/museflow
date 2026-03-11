from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class OAuthProviderTokenPayload:
    """Represents the raw, transient OAuth2 token data from an external provider.

    This schema is a Value Object used by provider clients to structure authentication
    credentials. It is not persisted and has no identity, serving purely as a data
    container for tokens and expiry information.
    """

    token_type: str
    access_token: str
    refresh_token: str
    expires_at: datetime
