import asyncio
import logging
from typing import Any
from typing import Final

from museflow.application.mappers.auth import to_auth_token_create_input
from museflow.application.mappers.auth import to_auth_token_update_input
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.domain.entities.auth import OAuthProviderUserToken
from museflow.domain.entities.user import User
from museflow.domain.enums import MusicProvider
from museflow.domain.exceptions import ProviderAuthTokenNotFoundError
from museflow.domain.exceptions import ProviderRateLimitExceededError
from museflow.domain.mappers.auth import to_token_payload
from museflow.infrastructure.adapters.http import RateLimitRetry
from museflow.infrastructure.adapters.providers.spotify.exceptions import SpotifyRefreshTokenInvalidError
from museflow.infrastructure.adapters.providers.spotify.exceptions import SpotifyTokenExpiredError
from museflow.infrastructure.adapters.providers.spotify.oauth import SpotifyOAuthAdapter
from museflow.infrastructure.config.settings.spotify import spotify_settings

logger = logging.getLogger(__name__)


class SpotifyOAuthSessionClient:
    """A stateful client for managing a user's Spotify session.

    This client handles the complexities of the user's session lifecycle, including:
    - Proactive token refresh: Refreshes the token if it's close to expiring.
    - Reactive token refresh: Refreshes the token upon receiving a 401 Unauthorized error.
    - Concurrent refreshes: a lock keeps this session's coroutines to one refresh, and a compare-and-swap in the
      database keeps a token refreshed or reconnected by another session meanwhile.
    """

    _RECONNECT_MESSAGE: Final[str] = "Spotify refresh token is no longer valid: reconnect the provider."

    def __init__(
        self,
        user: User,
        auth_token: OAuthProviderUserToken,
        uow: UnitOfWorkPort,
        oauth_client: SpotifyOAuthAdapter,
        token_buffer_seconds: int = spotify_settings.TOKEN_BUFFER_SECONDS,
    ) -> None:
        self.user = user
        self.auth_token = auth_token
        self.uow = uow
        self.oauth_client = oauth_client
        self.token_buffer_seconds = token_buffer_seconds

        self._refresh_lock = asyncio.Lock()

    async def execute(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        ignored_status_codes: frozenset[int] | None = None,
    ) -> dict[str, Any]:
        """Executes an authenticated API call, handling token refreshes automatically.

        This method first checks if the token needs a proactive refresh. If the API
        call fails with a token expiration error, it performs a reactive refresh
        and retries the call once.

        Args:
            method: The HTTP method for the API call.
            endpoint: The API endpoint to call.
            params: Optional query parameters.
            json_data: Optional JSON body for the request.
            ignored_status_codes: HTTP status codes that should not be logged as errors.
                Callers are responsible for handling these codes themselves.

        Returns:
            The JSON response from the API.

        Raises:
            SpotifyTokenExpiredError: If the token is still expired after a refresh attempt.
            ProviderAuthTokenNotFoundError: If the refresh token has expired or been revoked by
                Spotify (`invalid_grant`). The stored token is discarded and the user must
                reconnect via the OAuth sign-in flow.
        """
        # Proactive refresh check: prevents unnecessary 401s if we already know it's expired
        if self.auth_token.is_expired(buffer_seconds=self.token_buffer_seconds):
            await self._refresh_token_safely()

        current_access_token = self.auth_token.token_access

        try:
            response = await self.oauth_client.make_api_call(
                method=method,
                endpoint=endpoint,
                token_payload=to_token_payload(self.auth_token),
                params=params,
                json_data=json_data,
                ignored_status_codes=ignored_status_codes,
            )

        except SpotifyTokenExpiredError:
            # Reactive refresh as we got a 401 from the provider
            await self._refresh_token_safely(stale_access_token=current_access_token)

            # Retry only ONCE with new token and if it fails again with 401, bubble up the error (session invalid)
            try:
                return await self.oauth_client.make_api_call(
                    method=method,
                    endpoint=endpoint,
                    token_payload=to_token_payload(self.auth_token),
                    params=params,
                    json_data=json_data,
                    ignored_status_codes=ignored_status_codes,
                )
            except RateLimitRetry as e:
                raise ProviderRateLimitExceededError("Spotify rate limit exceeded after max retries") from e

        except RateLimitRetry as e:
            raise ProviderRateLimitExceededError("Spotify rate limit exceeded after max retries") from e

        return response

    async def _refresh_token_safely(self, stale_access_token: str | None = None) -> None:
        """Refreshes the access token, once for all the coroutines of this session.

        When another session replaced the stored token meanwhile, its token is taken over instead.

        Args:
            stale_access_token: The access token that was found to be expired.
                                This is used to ensure the token hasn't already
                                been refreshed by another coroutine.

        Raises:
            ProviderAuthTokenNotFoundError: If Spotify rejects the refresh token (`invalid_grant`) and no other
                session replaced it: the stored token is discarded so the user must reconnect via the OAuth sign-in
                flow.
        """
        # Fast check (outside lock)
        if self._should_skip_refresh(stale_access_token):
            return

        async with self._refresh_lock:
            # Double check (inside lock)
            if self._should_skip_refresh(stale_access_token):
                return

            # The lock only guards this session's coroutines: another session of the user (a concurrent request,
            # a reconnect) may replace the stored token at any time, so each write below holds only if the token is
            # still the one this session read (compare-and-swap); otherwise the newer token wins.
            stale_token = self.auth_token
            try:
                token_payload = await self.oauth_client.refresh_access_token(stale_token.token_refresh)
            except SpotifyRefreshTokenInvalidError as e:
                async with self.uow as uow:
                    discarded = await uow.auth_tokens.delete(
                        user_id=self.user.id,
                        provider=MusicProvider.SPOTIFY,
                        expected_token_refresh=stale_token.token_refresh,
                    )
                    auth_token = (
                        None
                        if discarded
                        else await uow.auth_tokens.get(user_id=self.user.id, provider=MusicProvider.SPOTIFY)
                    )
                if auth_token is None:
                    logger.warning(
                        "Spotify refresh token invalid — user must reconnect",
                        extra={"user_id": str(self.user.id), "provider": MusicProvider.SPOTIFY},
                    )
                    raise ProviderAuthTokenNotFoundError(self._RECONNECT_MESSAGE) from e
                self.auth_token = auth_token
                return

            # Committed right away: the new token must survive a later failure of the command
            async with self.uow as uow:
                auth_token = await uow.auth_tokens.update(
                    user_id=self.user.id,
                    provider=MusicProvider.SPOTIFY,
                    auth_token_in=to_auth_token_update_input(token_payload),
                    expected_token_access=stale_token.token_access,
                )
                if auth_token is None:
                    auth_token = await uow.auth_tokens.get(user_id=self.user.id, provider=MusicProvider.SPOTIFY)
                if auth_token is None:
                    # Deleted meanwhile, e.g. by a session whose refresh token Spotify rejected once this refresh
                    # rotated it, before this one was saved: the token Spotify just issued is valid, so it is saved.
                    auth_token = await uow.auth_tokens.upsert(
                        user_id=self.user.id,
                        provider=MusicProvider.SPOTIFY,
                        auth_token_in=to_auth_token_create_input(token_payload),
                    )
            self.auth_token = auth_token

    def _should_skip_refresh(self, stale_access_token: str | None) -> bool:
        if stale_access_token is None:
            # Proactive case: Skip if token is NOT expired
            return not self.auth_token.is_expired(buffer_seconds=self.token_buffer_seconds)

        # Reactive case: Skip if token has already changed from the stale one
        return self.auth_token.token_access != stale_access_token
