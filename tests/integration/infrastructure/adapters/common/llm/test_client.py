import os
from collections.abc import AsyncGenerator

from pydantic import BaseModel
from pydantic import HttpUrl

import pytest
from tenacity import stop_after_attempt

from museflow.infrastructure.adapters.common.llm.client import OpenRouterClient
from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.config.settings.openrouter import LLMSettings


class Answer(BaseModel):
    value: int


@pytest.mark.wiremock("openrouter")
class TestOpenRouterClient:
    @pytest.fixture
    async def openrouter_client(self, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[OpenRouterClient]:
        monkeypatch.setattr(OpenRouterClient.make_api_call.retry, "stop", stop_after_attempt(1))

        async with OpenRouterClient(
            api_key="dummy-api-key",
            base_url=HttpUrl(os.environ["WIREMOCK_OPENROUTER_BASE_URL"]),
            verify_ssl=False,
        ) as client:
            yield client

    async def test__complete__nominal(self, openrouter_client: OpenRouterClient) -> None:
        result = await openrouter_client.complete(
            [ChatMessage(role="user", content="Integration test of the OpenRouter client")],
            response_model=Answer,
            schema=JsonSchemaProperty.object({"value": JsonSchemaProperty.integer()}),
            llm=LLMSettings(MODEL="google/gemini-2.5-flash"),
            adapter="test",
        )

        assert result == Answer(value=42)

    async def test__check_models__nominal(self, openrouter_client: OpenRouterClient) -> None:
        await openrouter_client.check_models({"enricher": LLMSettings(MODEL="google/gemini-3.1-flash-lite")})
