from types import TracebackType
from typing import Any
from typing import Self

import httpx
from httpx import codes

from pydantic import HttpUrl

from tenacity import retry
from tenacity import retry_if_exception
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from museflow.infrastructure.config.settings.app import app_settings


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, httpx.HTTPStatusError):  # Retry 429 and 5xx only
        return exception.response.status_code == codes.TOO_MANY_REQUESTS or exception.response.status_code >= 500

    if isinstance(exception, httpx.RequestError):  # Retry network errors
        return True

    return False


class HttpClientMixin:
    """Generic HTTP mixin for infrastructure adapters.

    Provides shared httpx client setup, retry logic (5xx + 429 + network errors),
    and lifecycle management (close / async context manager). Concrete adapters
    combine this mixin with the relevant port (ProviderClientPort, AdvisorClientPort)
    via multiple inheritance.

    Split into separate mixins only if provider and advisor retry/transport concerns
    genuinely diverge.
    """

    def __init__(self, base_url: HttpUrl, verify_ssl: bool = True, timeout: float = 30.0) -> None:
        self._base_url = base_url
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            verify=verify_ssl,
            timeout=timeout,
            follow_redirects=True,
        )

    @property
    def base_url(self) -> HttpUrl:
        return self._base_url

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=wait_exponential(multiplier=1, min=2, max=60),  # 2 + 4 + 8 + 16 + 32 = 62 seconds
        stop=stop_after_attempt(app_settings.HTTP_MAX_RETRIES),
        reraise=True,
    )
    async def make_api_call(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response = await self._client.request(
            method=method.upper(),
            url=f"{str(self._base_url).rstrip('/')}{endpoint}",
            headers=headers,
            params=params,
            json=json_data,
        )
        response.raise_for_status()

        if response.status_code == codes.NO_CONTENT:
            return {}

        return response.json()

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()
