import json
from collections.abc import AsyncGenerator
from collections.abc import Iterable
from typing import Any
from unittest import mock

import httpx
from httpx import codes

from pydantic import BaseModel
from pydantic import HttpUrl

import pytest
from pytest_httpx import HTTPXMock

from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.adapters.common.llm.client import _is_retryable_error
from museflow.infrastructure.adapters.common.llm.exceptions import LLMModelError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRateLimitError
from museflow.infrastructure.adapters.common.llm.exceptions import LLMRequestError
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.adapters.common.llm.types import ReasoningEffort
from museflow.infrastructure.adapters.http import RateLimitRetry
from museflow.infrastructure.config.settings.openrouter import LLMSettings

URL = "https://openrouter.test/api/v1/chat/completions"
MODELS_URL = "https://openrouter.test/api/v1/models"

VALID_RESPONSE: dict[str, Any] = {
    "model": "google/gemini-2.5-flash",
    "choices": [{"message": {"role": "assistant", "content": '{"value": 42}'}, "finish_reason": "stop"}],
}
INVALID_RESPONSE: dict[str, Any] = {
    "model": "google/gemini-2.5-flash",
    "choices": [{"message": {"role": "assistant", "content": '{"value": "nope"}'}, "finish_reason": "stop"}],
}
CATALOG: dict[str, Any] = {
    "data": [
        {"id": "google/gemini-2.5-flash", "supported_parameters": ["structured_outputs", "reasoning", "temperature"]},
        {"id": "openai/gpt-5-mini", "supported_parameters": ["structured_outputs", "reasoning", "temperature"]},
        {"id": "mistralai/mistral-small", "supported_parameters": ["structured_outputs"]},
        {"id": "meta-llama/llama-3-8b-instruct"},
    ]
}
SCHEMA = JsonSchemaProperty.object({"value": JsonSchemaProperty.integer()})


class Answer(BaseModel):
    value: int


class TestOpenRouterClient:
    @pytest.fixture
    async def client(self) -> AsyncGenerator[OpenRouterClient]:
        async with OpenRouterClient(
            api_key="dummy-api-key",
            base_url=HttpUrl("https://openrouter.test/api/v1/"),
            max_retry_wait=5,
        ) as client:
            yield client

    @pytest.fixture
    def llm(self) -> LLMSettings:
        return LLMSettings(MODEL="google/gemini-2.5-flash")

    @pytest.fixture
    def messages(self) -> list[ChatMessage]:
        return [ChatMessage(role="user", content="prompt")]

    @pytest.fixture
    def mock_tenacity_sleep(self) -> Iterable[None]:
        retry_controller = OpenRouterClient.make_api_call.retry
        original_sleep = retry_controller.sleep

        retry_controller.sleep = mock.AsyncMock(return_value=None)
        yield
        retry_controller.sleep = original_sleep

    @pytest.fixture
    def mock_asyncio_sleep(self) -> Iterable[mock.AsyncMock]:
        with mock.patch("asyncio.sleep", new_callable=mock.AsyncMock) as mock_sleep:
            yield mock_sleep

    async def test__complete__nominal(
        self,
        client: OpenRouterClient,
        llm: LLMSettings,
        messages: list[ChatMessage],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=VALID_RESPONSE)

        result = await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

        assert result == Answer(value=42)
        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"] == "Bearer dummy-api-key"
        assert json.loads(request.content) == {
            "model": "google/gemini-2.5-flash",
            "messages": [{"role": "user", "content": "prompt"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "Answer", "strict": True, "schema": SCHEMA.model_dump(exclude_none=True)},
            },
            "provider": {"require_parameters": True, "zdr": True, "data_collection": "deny"},
        }

    async def test__complete__sends_step_tuning(
        self,
        client: OpenRouterClient,
        messages: list[ChatMessage],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=VALID_RESPONSE)
        llm = LLMSettings(
            MODEL="google/gemini-2.5-flash",
            MAX_TOKENS=2000,
            REASONING_EFFORT=ReasoningEffort.LOW,
            TEMPERATURE=0.3,
            FALLBACK_MODELS=["openai/gpt-5-mini"],
        )

        await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["models"] == ["google/gemini-2.5-flash", "openai/gpt-5-mini"]
        assert body["max_tokens"] == 2000
        assert body["reasoning"] == {"effort": "low"}
        assert body["temperature"] == 0.3

    async def test__complete__zdr_disabled(
        self,
        llm: LLMSettings,
        messages: list[ChatMessage],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=VALID_RESPONSE)

        async with OpenRouterClient(
            api_key="dummy-api-key",
            base_url=HttpUrl("https://openrouter.test/api/v1/"),
            zdr=False,
        ) as client:
            await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

        body = json.loads(httpx_mock.get_requests()[0].content)
        assert body["provider"] == {"require_parameters": True, "zdr": False, "data_collection": "deny"}

    async def test__complete__self_heals_invalid_reply(
        self,
        client: OpenRouterClient,
        llm: LLMSettings,
        messages: list[ChatMessage],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", json=INVALID_RESPONSE)
        httpx_mock.add_response(url=URL, method="POST", json=VALID_RESPONSE)

        result = await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

        assert result == Answer(value=42)
        retried = json.loads(httpx_mock.get_requests()[1].content)
        assert [message["role"] for message in retried["messages"]] == ["user", "assistant", "user"]

    async def test__complete__429_with_retry_after__sleeps_and_retries(
        self,
        client: OpenRouterClient,
        llm: LLMSettings,
        messages: list[ChatMessage],
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
        mock_asyncio_sleep: mock.AsyncMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL, method="POST", status_code=codes.TOO_MANY_REQUESTS, headers={"Retry-After": "3"}
        )
        httpx_mock.add_response(url=URL, method="POST", json=VALID_RESPONSE)

        result = await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

        assert result == Answer(value=42)
        mock_asyncio_sleep.assert_awaited_once_with(4)

    async def test__complete__429_with_retry_after_above_max__raises_rate_limit(
        self,
        client: OpenRouterClient,
        llm: LLMSettings,
        messages: list[ChatMessage],
        httpx_mock: HTTPXMock,
        mock_asyncio_sleep: mock.AsyncMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL, method="POST", status_code=codes.TOO_MANY_REQUESTS, headers={"Retry-After": "10"}
        )

        with pytest.raises(LLMRateLimitError, match="exceeds max wait 5s"):
            await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

        assert len(httpx_mock.get_requests()) == 1
        mock_asyncio_sleep.assert_not_awaited()

    @pytest.mark.parametrize("headers", [{"Retry-After": "1"}, {}], ids=["with_retry_after", "without_retry_after"])
    async def test__complete__429_exhausted__raises_rate_limit(
        self,
        client: OpenRouterClient,
        llm: LLMSettings,
        messages: list[ChatMessage],
        headers: dict[str, str],
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
        mock_asyncio_sleep: mock.AsyncMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL, method="POST", status_code=codes.TOO_MANY_REQUESTS, headers=headers, is_reusable=True
        )

        with pytest.raises(LLMRateLimitError, match="after max retries"):
            await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

        assert len(httpx_mock.get_requests()) > 1

    async def test__complete__503__raises_request_error_without_retry(
        self,
        client: OpenRouterClient,
        llm: LLMSettings,
        messages: list[ChatMessage],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(
            url=URL,
            method="POST",
            status_code=codes.SERVICE_UNAVAILABLE,
            json={"error": {"code": 503, "message": "No available model provider meets your routing requirements"}},
        )

        with pytest.raises(LLMRequestError) as exc_info:
            await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

        assert exc_info.value.status_code == codes.SERVICE_UNAVAILABLE
        assert exc_info.value.model == "google/gemini-2.5-flash"
        assert exc_info.value.adapter == "test"
        assert "google/gemini-2.5-flash" in str(exc_info.value)
        assert "routing requirements" in str(exc_info.value)
        assert len(httpx_mock.get_requests()) == 1

    async def test__complete__4xx_without_json_body__uses_raw_text(
        self,
        client: OpenRouterClient,
        llm: LLMSettings,
        messages: list[ChatMessage],
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", status_code=codes.UNAUTHORIZED, text="Unauthorized")

        with pytest.raises(LLMRequestError, match="Unauthorized"):
            await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

    async def test__complete__5xx__retries_then_succeeds(
        self,
        client: OpenRouterClient,
        llm: LLMSettings,
        messages: list[ChatMessage],
        httpx_mock: HTTPXMock,
        mock_tenacity_sleep: None,
    ) -> None:
        httpx_mock.add_response(url=URL, method="POST", status_code=codes.BAD_GATEWAY)
        httpx_mock.add_response(url=URL, method="POST", json=VALID_RESPONSE)

        result = await client.complete(messages, response_model=Answer, schema=SCHEMA, llm=llm, adapter="test")

        assert result == Answer(value=42)

    async def test__check_models__nominal(self, client: OpenRouterClient, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url=MODELS_URL, method="GET", json=CATALOG)
        llm = LLMSettings(
            MODEL="google/gemini-2.5-flash",
            REASONING_EFFORT=ReasoningEffort.LOW,
            TEMPERATURE=0.3,
            FALLBACK_MODELS=["openai/gpt-5-mini:nitro"],
        )

        await client.check_models({"enricher": llm, "advisor": LLMSettings(MODEL="openai/gpt-5-mini")})

        assert len(httpx_mock.get_requests()) == 1
        assert "Authorization" not in httpx_mock.get_requests()[0].headers

    @pytest.mark.parametrize(
        ("llm", "expected_model", "expected_message"),
        [
            pytest.param(
                LLMSettings(MODEL="google/gemni-2.5-flash"),
                "google/gemni-2.5-flash",
                "Unknown OpenRouter model 'google/gemni-2.5-flash' for the enricher step. "
                "Did you mean 'google/gemini-2.5-flash'?",
                id="typo",
            ),
            pytest.param(
                LLMSettings(MODEL="google/gemini-2.5-flash", FALLBACK_MODELS=["foo"]),
                "foo",
                "Unknown OpenRouter model 'foo' for the enricher step. See https://openrouter.ai/models.",
                id="unknown_fallback",
            ),
            pytest.param(
                LLMSettings(MODEL="meta-llama/llama-3-8b-instruct"),
                "meta-llama/llama-3-8b-instruct",
                "OpenRouter model 'meta-llama/llama-3-8b-instruct' for the enricher step does not support: "
                "structured_outputs.",
                id="no_structured_outputs",
            ),
            pytest.param(
                LLMSettings(MODEL="mistralai/mistral-small", REASONING_EFFORT=ReasoningEffort.HIGH, MAX_TOKENS=1000),
                "mistralai/mistral-small",
                "OpenRouter model 'mistralai/mistral-small' for the enricher step does not support: "
                "reasoning, max_tokens.",
                id="missing_step_parameters",
            ),
        ],
    )
    async def test__check_models__invalid(
        self,
        client: OpenRouterClient,
        llm: LLMSettings,
        expected_model: str,
        expected_message: str,
        httpx_mock: HTTPXMock,
    ) -> None:
        httpx_mock.add_response(url=MODELS_URL, method="GET", json=CATALOG)

        with pytest.raises(LLMModelError) as exc_info:
            await client.check_models({"enricher": llm})

        assert str(exc_info.value) == expected_message
        assert exc_info.value.step == "enricher"
        assert exc_info.value.model == expected_model

    @pytest.mark.parametrize(
        ("exception", "expected"),
        [
            pytest.param(LLMRateLimitError(), False, id="rate_limit_exhausted"),
            pytest.param(RateLimitRetry(), True, id="rate_limit_retry"),
            pytest.param(httpx.ConnectError("boom"), True, id="network"),
            pytest.param(ValueError(), False, id="other"),
        ],
    )
    def test__is_retryable_error(self, exception: BaseException, expected: bool) -> None:
        assert _is_retryable_error(exception) is expected

    @pytest.mark.parametrize(
        ("status_code", "expected"),
        [
            pytest.param(codes.BAD_REQUEST, False, id="400"),
            pytest.param(codes.REQUEST_TIMEOUT, True, id="408"),
            pytest.param(codes.TOO_MANY_REQUESTS, True, id="429"),
            pytest.param(codes.INTERNAL_SERVER_ERROR, True, id="500"),
            pytest.param(codes.SERVICE_UNAVAILABLE, False, id="503"),
        ],
    )
    def test__is_retryable_error__http_status(self, status_code: int, expected: bool) -> None:
        response = httpx.Response(status_code, request=httpx.Request("POST", URL))
        exception = httpx.HTTPStatusError("error", request=response.request, response=response)

        assert _is_retryable_error(exception) is expected
