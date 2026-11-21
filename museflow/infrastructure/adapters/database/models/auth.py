import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import LargeBinary
from sqlalchemy import String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from museflow.application.ports.security import TokenCipherPort
from museflow.domain.entities.auth import OAuthProviderState
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.enums import MusicProvider
from museflow.infrastructure.adapters.database.models.base import Base
from museflow.infrastructure.adapters.database.models.base import DatetimeTrackMixin
from museflow.infrastructure.adapters.database.models.base import NumericIdMixin


class AuthProviderStateModel(NumericIdMixin, DatetimeTrackMixin, Base, kw_only=True):
    """SQLAlchemy model for storing OAuth provider state.

    This model is used to persist the state token generated during the OAuth flow,
    linking it to a user and a specific music provider.
    """

    __tablename__ = "museflow_auth_state"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False)

    state: Mapped[str] = mapped_column(String(512), nullable=False, index=True, unique=True)

    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider_auth_state"),)

    def to_entity(self) -> OAuthProviderState:
        return OAuthProviderState(
            id=self.id,
            user_id=self.user_id,
            provider=self.provider,
            state=self.state,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class AuthProviderTokenModel(NumericIdMixin, Base, kw_only=True):
    """SQLAlchemy model for storing OAuth provider user tokens.

    This model persists the access and refresh tokens for a user, allowing the
    application to make authenticated API calls to the music provider on their behalf.

    Note: DatetimeTrackMixin is intentionally omitted — token rows are identified
    by their expiry (token_expires_at), not by generic created_at/updated_at timestamps.
    """

    __tablename__ = "museflow_auth_token"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("museflow_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[MusicProvider] = mapped_column(Enum(MusicProvider), nullable=False)

    token_type: Mapped[str] = mapped_column(String(512), nullable=False)
    # Encrypted by the repository (`TokenCipherPort`), never in clear: no length limit, as the provider sets the
    # length of its tokens and Spotify's grew before
    token_access: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    token_refresh: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider_auth_token"),)

    def to_entity(self, token_cipher: TokenCipherPort) -> OAuthProviderUserToken:
        """The entity, with its tokens decrypted.

        Raises:
            TokenDecryptionError: If a token was encrypted with another key, or altered.
        """
        return OAuthProviderUserToken(
            id=self.id,
            user_id=self.user_id,
            provider=self.provider,
            token_type=self.token_type,
            token_access=token_cipher.decrypt(
                self.token_access,
                context=self.get_token_context(self.user_id, self.provider, "token_access"),
            ),
            token_refresh=token_cipher.decrypt(
                self.token_refresh,
                context=self.get_token_context(self.user_id, self.provider, "token_refresh"),
            ),
            token_expires_at=self.token_expires_at,
        )

    @staticmethod
    def get_token_context(user_id: uuid.UUID, provider: MusicProvider, column: str) -> str:
        """The context a token is encrypted for: its row and column, so that bytes copied to another user, provider or
        column fail to decrypt."""
        return f"{user_id}:{provider}:{column}"
