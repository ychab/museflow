from museflow.infrastructure.adapters.common.gemini.schemas import GeminiCandidate
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerateContentRequest
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiGenerationConfig
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiRequestPart
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiResponse
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiResponseContent
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiResponsePart
from museflow.infrastructure.adapters.common.gemini.schemas import GeminiSchemaProperty


class TestGeminiSchemaProperty:
    def test__leaf_node__excludes_none_on_dump(self) -> None:
        prop = GeminiSchemaProperty(type="string")
        dumped = prop.model_dump(exclude_none=True)
        assert dumped == {"type": "string"}
        assert "items" not in dumped
        assert "properties" not in dumped
        assert "required" not in dumped

    def test__array_with_items(self) -> None:
        prop = GeminiSchemaProperty(type="array", items=GeminiSchemaProperty(type="string"))
        dumped = prop.model_dump(exclude_none=True)
        assert dumped == {"type": "array", "items": {"type": "string"}}

    def test__object_with_properties_and_required(self) -> None:
        prop = GeminiSchemaProperty(
            type="object",
            properties={"name": GeminiSchemaProperty(type="string")},
            required=["name"],
        )
        dumped = prop.model_dump(exclude_none=True)
        assert dumped == {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }


class TestGeminiGenerateContentRequest:
    def test__dump__top_level_keys(self) -> None:
        request = GeminiGenerateContentRequest(
            contents=[GeminiRequestContent(parts=[GeminiRequestPart(text="prompt")])],
            generationConfig=GeminiGenerationConfig(
                responseMimeType="application/json",
                responseSchema=GeminiSchemaProperty(type="object"),
            ),
        )
        dumped = request.model_dump(exclude_none=True)
        assert "contents" in dumped
        assert "generationConfig" in dumped
        assert dumped["contents"][0]["parts"][0]["text"] == "prompt"
        assert dumped["generationConfig"]["responseMimeType"] == "application/json"

    def test__dump__excludes_none_fields(self) -> None:
        request = GeminiGenerateContentRequest(
            contents=[GeminiRequestContent(parts=[GeminiRequestPart(text="prompt")])],
            generationConfig=GeminiGenerationConfig(
                responseMimeType="application/json",
                responseSchema=GeminiSchemaProperty(type="string"),
            ),
        )
        schema_dump = request.model_dump(exclude_none=True)["generationConfig"]["responseSchema"]
        assert "items" not in schema_dump
        assert "properties" not in schema_dump
        assert "required" not in schema_dump


class TestGeminiResponse:
    def test__parse__nominal(self) -> None:
        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": '{"tracks": []}'}],
                        "role": "model",
                    }
                }
            ]
        }
        response = GeminiResponse.model_validate(data)
        assert len(response.candidates) == 1
        content = response.candidates[0].content
        assert content is not None
        assert content.role == "model"
        assert content.parts[0].text == '{"tracks": []}'

    def test__parse__empty_candidates_default(self) -> None:
        response = GeminiResponse.model_validate({})
        assert response.candidates == []

    def test__parse__explicit_empty_candidates(self) -> None:
        response = GeminiResponse.model_validate({"candidates": []})
        assert response.candidates == []

    def test__candidate_roundtrip(self) -> None:
        candidate = GeminiCandidate(
            content=GeminiResponseContent(
                parts=[GeminiResponsePart(text="hello")],
                role="model",
            )
        )
        assert candidate.content is not None
        assert candidate.content.parts[0].text == "hello"

    def test__parse__finish_reason(self) -> None:
        response = GeminiResponse.model_validate(
            {"candidates": [{"content": {"parts": [{"text": "{}"}], "role": "model"}, "finishReason": "MAX_TOKENS"}]}
        )
        assert response.candidates[0].finishReason == "MAX_TOKENS"

    def test__parse__candidate_without_content(self) -> None:
        response = GeminiResponse.model_validate({"candidates": [{"finishReason": "SAFETY"}]})
        assert response.candidates[0].content is None

    def test__parse__content_without_parts_nor_role(self) -> None:
        response = GeminiResponse.model_validate({"candidates": [{"content": {}}]})
        content = response.candidates[0].content
        assert content is not None
        assert content.parts == []
        assert content.role is None


class TestGeminiRequestContent:
    def test__dump__excludes_unset_role(self) -> None:
        content = GeminiRequestContent(parts=[GeminiRequestPart(text="hi")])
        assert content.model_dump(exclude_none=True) == {"parts": [{"text": "hi"}]}

    def test__dump__includes_role(self) -> None:
        content = GeminiRequestContent(role="model", parts=[GeminiRequestPart(text="hi")])
        assert content.model_dump(exclude_none=True) == {"role": "model", "parts": [{"text": "hi"}]}
