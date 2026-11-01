import asyncio
import difflib
import logging
from collections import defaultdict
from collections.abc import Mapping
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

from museflow.infrastructure.adapters.common.llm.exceptions import LLMModelError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRateLimitError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRequestError
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.adapters.common.llm.schemas import ChatCompletionRequest
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.adapters.common.llm.schemas import JsonSchemaFormat
from museflow.infrastructure.adapters.common.llm.schemas import ModelCatalogResponse
from museflow.infrastructure.adapters.common.llm.schemas import ProviderPreferences
from museflow.infrastructure.adapters.common.llm.schemas import ReasoningConfig
from museflow.infrastructure.adapters.common.llm.schemas import ResponseFormat
from museflow.infrastructure.adapters.common.llm.schemas import ZdrEndpointsResponse
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


def _required_parameters(llm: LLMSettings) -> list[str]:
    """Parameters the request carries for this step, which `require_parameters` makes mandatory for the provider."""
    optional = {
        "reasoning": llm.REASONING_EFFORT is not None,
        "temperature": llm.TEMPERATURE is not None,
        "max_tokens": llm.MAX_TOKENS is not None,
    }
    return ["structured_outputs", *(name for name, sent in optional.items() if sent)]


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

    async def check_models(self, steps: Mapping[str, LLMSettings]) -> None:
        """Fails fast on a misconfigured model, before any paid call, against OpenRouter's public listings.

        Each step's model and fallbacks must exist and support the parameters the step sends; with ZDR on, they must
        also have a Zero Data Retention endpoint supporting them. This is a necessary condition only: OpenRouter picks
        the provider endpoint at request time.

        Raises:
            LLMModelError: If a model is unknown, lacks a required parameter or, with ZDR on, a ZDR endpoint.
        """
        response_data = await self.make_api_call(method="GET", endpoint="/models")
        catalog = {model.id: model for model in ModelCatalogResponse.model_validate(response_data).data}

        for step, llm in steps.items():
            for model_id in [llm.MODEL, *llm.FALLBACK_MODELS]:
                # Routing shortcuts (`:nitro`, `:floor`, `:online`…) are not listed: check the base model instead
                model = catalog.get(model_id) or catalog.get(model_id.partition(":")[0])
                if model is None:
                    suggestions = difflib.get_close_matches(model_id, catalog, n=1)
                    hint = (
                        f" Did you mean '{suggestions[0]}'?" if suggestions else " See https://openrouter.ai/models."
                    )
                    raise LLMModelError(
                        f"Unknown OpenRouter model '{model_id}' for the {step} step.{hint}", step=step, model=model_id
                    )

                missing = [param for param in _required_parameters(llm) if param not in model.supported_parameters]
                if missing:
                    raise LLMModelError(
                        f"OpenRouter model '{model_id}' for the {step} step does not support: {', '.join(missing)}.",
                        step=step,
                        model=model_id,
                    )

        if self._zdr:
            await self._check_zdr_endpoints(steps)

        logger.debug(f"OpenRouter models checked for steps: {', '.join(steps)}")

    async def _check_zdr_endpoints(self, steps: Mapping[str, LLMSettings]) -> None:
        response_data = await self.make_api_call(method="GET", endpoint="/endpoints/zdr")
        zdr_parameters: dict[str, set[str]] = defaultdict(set)
        for endpoint in ZdrEndpointsResponse.model_validate(response_data).data:
            zdr_parameters[endpoint.model_id].update(endpoint.supported_parameters)

        for step, llm in steps.items():
            for model_id in [llm.MODEL, *llm.FALLBACK_MODELS]:
                listed_id = model_id if model_id in zdr_parameters else model_id.partition(":")[0]
                if listed_id not in zdr_parameters:
                    raise LLMModelError(
                        f"OpenRouter model '{model_id}' for the {step} step has no Zero Data Retention endpoint. "
                        f"Pick another model (GET {str(self._base_url).rstrip('/')}/endpoints/zdr lists them) "
                        "or set OPENROUTER_ZDR=false.",
                        step=step,
                        model=model_id,
                    )

                missing = [param for param in _required_parameters(llm) if param not in zdr_parameters[listed_id]]
                if missing:
                    raise LLMModelError(
                        f"OpenRouter model '{model_id}' for the {step} step does not support on its Zero Data "
                        f"Retention endpoints: {', '.join(missing)}.",
                        step=step,
                        model=model_id,
                    )

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
