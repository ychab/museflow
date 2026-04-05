from pydantic import BaseModel
from pydantic import Field

# --- Request models ---


class GeminiSchemaProperty(BaseModel):
    type: str
    items: "GeminiSchemaProperty | None" = None
    properties: "dict[str, GeminiSchemaProperty] | None" = None
    required: list[str] | None = None
    additionalProperties: "GeminiSchemaProperty | None" = None

    @classmethod
    def string(cls) -> "GeminiSchemaProperty":
        return cls(type="string")

    @classmethod
    def number(cls) -> "GeminiSchemaProperty":
        return cls(type="number")

    @classmethod
    def array(cls, items: "GeminiSchemaProperty") -> "GeminiSchemaProperty":
        return cls(type="array", items=items)

    @classmethod
    def object(
        cls,
        properties: "dict[str, GeminiSchemaProperty]",
        required: list[str] | None = None,
    ) -> "GeminiSchemaProperty":
        return cls(type="object", properties=properties, required=required)


GeminiSchemaProperty.model_rebuild()


class GeminiGenerationConfig(BaseModel):
    responseMimeType: str
    responseSchema: GeminiSchemaProperty


class GeminiRequestPart(BaseModel):
    text: str


class GeminiRequestContent(BaseModel):
    parts: list[GeminiRequestPart]


class GeminiGenerateContentRequest(BaseModel):
    contents: list[GeminiRequestContent]
    generationConfig: GeminiGenerationConfig


# --- Response models ---


class GeminiResponsePart(BaseModel):
    text: str


class GeminiResponseContent(BaseModel):
    parts: list[GeminiResponsePart]
    role: str


class GeminiCandidate(BaseModel):
    content: GeminiResponseContent


class GeminiResponse(BaseModel):
    candidates: list[GeminiCandidate] = Field(default_factory=list)
