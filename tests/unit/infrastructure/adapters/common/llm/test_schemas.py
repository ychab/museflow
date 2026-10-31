from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.adapters.common.llm.schemas import ChatCompletionRequest
from museflow.infrastructure.adapters.common.llm.schemas import ChatCompletionResponse
from museflow.infrastructure.adapters.common.llm.schemas import ChatMessage
from museflow.infrastructure.adapters.common.llm.schemas import JsonSchemaFormat
from museflow.infrastructure.adapters.common.llm.schemas import ProviderPreferences
from museflow.infrastructure.adapters.common.llm.schemas import ReasoningConfig
from museflow.infrastructure.adapters.common.llm.schemas import ResponseFormat
from museflow.infrastructure.types import ReasoningEffort


class TestChatCompletionRequest:
    def test__dump__matches_openrouter_shape(self) -> None:
        request = ChatCompletionRequest(
            model="google/gemini-2.5-flash",
            models=["google/gemini-2.5-flash", "openai/gpt-5-mini"],
            messages=[ChatMessage(role="system", content="role"), ChatMessage(role="user", content="prompt")],
            response_format=ResponseFormat(
                json_schema=JsonSchemaFormat(name="Answer", schema_=JsonSchemaProperty.object({}))
            ),
            max_tokens=1000,
            temperature=0.2,
            reasoning=ReasoningConfig(effort=ReasoningEffort.HIGH),
            provider=ProviderPreferences(zdr=True),
        )

        assert request.model_dump(exclude_none=True, by_alias=True) == {
            "model": "google/gemini-2.5-flash",
            "models": ["google/gemini-2.5-flash", "openai/gpt-5-mini"],
            "messages": [{"role": "system", "content": "role"}, {"role": "user", "content": "prompt"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "Answer",
                    "strict": True,
                    "schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
                },
            },
            "max_tokens": 1000,
            "temperature": 0.2,
            "reasoning": {"effort": "high"},
            "provider": {"require_parameters": True, "zdr": True, "data_collection": "deny"},
        }

    def test__dump__omits_unset_tuning(self) -> None:
        request = ChatCompletionRequest(
            model="google/gemini-2.5-flash",
            messages=[ChatMessage(role="user", content="prompt")],
            response_format=ResponseFormat(
                json_schema=JsonSchemaFormat(name="Answer", schema_=JsonSchemaProperty.object({}))
            ),
            provider=ProviderPreferences(zdr=False),
        )

        dumped = request.model_dump(exclude_none=True, by_alias=True)

        assert set(dumped) == {"model", "messages", "response_format", "provider"}


class TestChatCompletionResponse:
    def test__defaults__empty_body(self) -> None:
        response = ChatCompletionResponse.model_validate({})

        assert response.model is None
        assert response.choices == []
        assert response.error is None

    def test__parses_choices_and_ignores_unknown_fields(self) -> None:
        response = ChatCompletionResponse.model_validate(
            {
                "id": "gen-123",
                "model": "google/gemini-2.5-flash",
                "choices": [
                    {"message": {"role": "assistant", "content": "{}"}, "finish_reason": "stop", "index": 0},
                ],
                "usage": {"cost": 0.0001},
            }
        )

        assert response.model == "google/gemini-2.5-flash"
        assert response.choices[0].message is not None
        assert response.choices[0].message.content == "{}"
        assert response.choices[0].finish_reason == "stop"
