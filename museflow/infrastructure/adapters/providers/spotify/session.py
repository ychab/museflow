import asyncio
from typing import Any

from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.mappers.auth import auth_token_from_token_payload
from museflow.domain.mappers.auth import auth_token_to_token_payload
from museflow.domain.mappers.auth import auth_token_update_from_token_payload
from museflow.domain.ports.repositories.auth import OAuthProviderTokenRepository
from museflow.domain.types import MusicProvider
from museflow.infrastructure.adapters.providers.spotify.client import SpotifyOAuthClientAdapter
from museflow.infrastructure.adapters.providers.spotify.exceptions import SpotifyTokenExpiredError
from museflow.infrastructure.config.settings.spotify import spotify_settings


class SpotifyOAuthSessionClient:
    """
    Stateful provider API client which handles user session lifecycle:
    - Proactive token refresh (if close to expiry)
    - Reactive token refresh (if 401 occurs)
    - Thread-safe DB updates (Locking)
    """

    def __init__(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        auth_token_repository: OAuthProviderTokenRepository,
        client: SpotifyOAuthClientAdapter,
        token_buffer_seconds: int = spotify_settings.TOKEN_BUFFER_SECONDS,
    ):
        self.user = user
        self.auth_token = auth_token
        self.auth_token_repository = auth_token_repository
        self.client = client
        self.token_buffer_seconds = token_buffer_seconds

        self._refresh_lock = asyncio.Lock()

    async def execute(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Proactive refresh check: prevents unnecessary 401s if we already know it's expired
        if self.auth_token.is_expired(buffer_seconds=self.token_buffer_seconds):
            await self._refresh_token_safely()

        current_access_token = self.auth_token.token_access

        try:
            response = await self.client.make_user_api_call(
                method=method,
                endpoint=endpoint,
                token_payload=auth_token_to_token_payload(self.auth_token),
                params=params,
                json_data=json_data,
            )

        except SpotifyTokenExpiredError:
            # Reactive refresh as we got a 401 from the provider
            await self._refresh_token_safely(stale_access_token=current_access_token)

            # Retry only ONCE with new token and if it fails again with 401, bubble up the error (session invalid)
            return await self.client.make_user_api_call(
                method=method,
                endpoint=endpoint,
                token_payload=auth_token_to_token_payload(self.auth_token),
                params=params,
                json_data=json_data,
            )

        return response

    async def _refresh_token_safely(self, stale_access_token: str | None = None) -> None:
        # Fast check (outside lock)
        if self._should_skip_refresh(stale_access_token):
            return

        async with self._refresh_lock:
            # Double check (inside lock)
            if self._should_skip_refresh(stale_access_token):
                return

            token_payload = await self.client.refresh_access_token(self.auth_token.token_refresh)

            # Update in DB
            await self.auth_token_repository.update(
                user_id=self.user.id,
                provider=MusicProvider.SPOTIFY,
                auth_token_data=auth_token_update_from_token_payload(token_payload),
            )

            # Update also in memory
            self.auth_token = auth_token_from_token_payload(
                auth_token_id=self.auth_token.id,
                user_id=self.user.id,
                provider=self.auth_token.provider,
                token_payload=token_payload,
            )

    def _should_skip_refresh(self, stale_access_token: str | None) -> bool:
        if stale_access_token is None:
            # Proactive case: Skip if token is NOT expired
            return not self.auth_token.is_expired(buffer_seconds=self.token_buffer_seconds)

        # Reactive case: Skip if token has already changed from the stale one
        return self.auth_token.token_access != stale_access_token
