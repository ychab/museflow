import asyncio
import logging
from typing import Any
from typing import cast

import httpx
from httpx import codes

from pydantic import BaseModel
from pydantic import HttpUrl

from tenacity import before_sleep_log
from tenacity import retry
from tenacity import retry_if_exception
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from museflow.infrastructure.adapters.common.llm.exceptions import LLMRateLimitError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRequestError
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.adapters.common.llm.schemas import ChatCompletionRequest
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.adapters.common.llm.schemas import JsonSchemaFormat
from museflow.infrastructure.adapters.common.llm.schemas import ProviderPreferences
from museflow.infrastructure.adapters.common.llm.schemas import ReasoningConfig
from museflow.infrastructure.adapters.common.llm.schemas import ResponseFormat
from museflow.infrastructure.adapters.common.llm.self_heal import self_heal
from museflow.infrastructure.adapters.common.llm.utils import parse_retry_after
from museflow.infrastructure.adapters.common.llm.validation import parse_completion
from museflow.infrastructure.adapters.http import HttpClientMixin
from museflow.infrastructure.adapters.http import RateLimitRetry
from museflow.infrastructure.config.settings.openrouter import LLMSettings
from museflow.infrastructure.config.settings.openrouter import openrouter_settings

logger = logging.getLogger(__name__)


def _is_retryable_error(exception: BaseException) -> bool:
    if isinstance(exception, LLMRateLimitError):
        return False  # Rate limit wait above the max — let it propagate

    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        if status_code == codes.SERVICE_UNAVAILABLE:
            return False  # No provider matches the routing rules (model, ZDR, parameters): retrying won't help
        return status_code in (codes.REQUEST_TIMEOUT, codes.TOO_MANY_REQUESTS) or status_code >= 500

    # Retry network error OR manual retry signal (used for 429 with Retry-After)
    if isinstance(exception, (httpx.RequestError, RateLimitRetry)):
        return True

    return False


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"]["message"])
    except KeyError, TypeError, ValueError:
        return response.text


class OpenRouterClient(HttpClientMixin):
    """Structured chat completions through the OpenRouter gateway, shared by the LLM adapters."""

    def __init__(
        self,
        api_key: str,
        base_url: HttpUrl | None = None,
        timeout: float = 180.0,
        verify_ssl: bool = True,
        max_retry_wait: int = 60,
        zdr: bool = True,
    ) -> None:
        super().__init__(
            base_url=base_url or openrouter_settings.BASE_URL,
            verify_ssl=verify_ssl,
            timeout=timeout,
        )
        self._api_key = api_key
        self._max_retry_wait = max_retry_wait
        self._zdr = zdr

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(openrouter_settings.HTTP_MAX_RETRIES),
        before_sleep=before_sleep_log(logger, logging.WARNING),
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
        try:
            response = await self._client.request(
                method=method.upper(),
                url=f"{str(self._base_url).rstrip('/')}{endpoint}",
                headers=headers,
                params=params,
                json=json_data,
            )
            response.raise_for_status()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == codes.TOO_MANY_REQUESTS:
                retry_delay = parse_retry_after(e.response)
                if retry_delay is not None:
                    if retry_delay > self._max_retry_wait:
                        logger.warning(
                            "OpenRouter rate limit wait exceeds max, aborting",
                            extra={"retry_delay": retry_delay, "max_retry_wait": self._max_retry_wait},
                        )
                        raise LLMRateLimitError(
                            f"OpenRouter rate limit {retry_delay}s exceeds max wait {self._max_retry_wait}s"
                        ) from e

                    logger.debug(f"OpenRouter rate limit exceeded, retrying in {retry_delay} seconds")
                    await asyncio.sleep(retry_delay + 1)
                    raise RateLimitRetry() from e

            raise

        return cast(dict[str, Any], response.json())

    @self_heal()
    async def complete[T: BaseModel](
        self,
        messages: list[ChatMessage],
        /,
        *,
        response_model: type[T],
        schema: JsonSchemaProperty,
        llm: LLMSettings,
        adapter: str,
    ) -> T:
        """Sends the conversation and parses the reply into `response_model`, constrained by `schema`.

        Raises:
            LLMRateLimitError: If OpenRouter keeps rate-limiting past the retry budget.
            LLMRequestError: If OpenRouter rejects the request, e.g. 503 when no provider endpoint serves the model
                with the required parameters and data policy.
            LLMResponseError: If the reply is unusable.
        """
        request = ChatCompletionRequest(
            model=llm.MODEL,
            models=[llm.MODEL, *llm.FALLBACK_MODELS] if llm.FALLBACK_MODELS else None,
            messages=messages,
            response_format=ResponseFormat(json_schema=JsonSchemaFormat(name=response_model.__name__, schema_=schema)),
            max_tokens=llm.MAX_TOKENS,
            temperature=llm.TEMPERATURE,
            reasoning=ReasoningConfig(effort=llm.REASONING_EFFORT) if llm.REASONING_EFFORT else None,
            provider=ProviderPreferences(zdr=self._zdr),
        )
        try:
            response_data = await self.make_api_call(
                method="POST",
                endpoint="/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json_data=request.model_dump(exclude_none=True, by_alias=True),
            )
        except RateLimitRetry as e:
            raise LLMRateLimitError(f"OpenRouter rate limit exceeded after max retries ({adapter})") from e
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == codes.TOO_MANY_REQUESTS:
                raise LLMRateLimitError(f"OpenRouter rate limit exceeded after max retries ({adapter})") from e

            logger.exception(
                "OpenRouter API error",
                extra={"status_code": status_code, "adapter": adapter, "model": llm.MODEL},
            )
            raise LLMRequestError(
                f"OpenRouter rejected the {adapter} request for model '{llm.MODEL}' "
                f"({status_code}): {_error_message(e.response)}",
                adapter=adapter,
                model=llm.MODEL,
                status_code=status_code,
            ) from e

        return parse_completion(response_data, response_model, adapter)
