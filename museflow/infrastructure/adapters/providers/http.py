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


class HttpProviderMixin:
    """HTTP mixin for provider adapters.

    Provides shared httpx client setup, a generic retried make_api_call with
    default Content-Type header merging, and lifecycle management. Concrete
    adapters combine this mixin with ProviderClientPort via multiple inheritance.
    """

    def __init__(
        self,
        base_url: HttpUrl,
        verify_ssl: bool = True,
        timeout: float = 30.0,
    ) -> None:
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
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = await self._client.request(
            method=method.upper(),
            url=f"{str(self._base_url).rstrip('/')}{endpoint}",
            headers={"Content-Type": "application/json"} | (headers or {}),
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
