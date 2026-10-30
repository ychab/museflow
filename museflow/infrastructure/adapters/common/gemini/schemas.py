from typing import Literal

from pydantic import BaseModel
from pydantic import Field

# --- Request models ---


class GeminiSchemaProperty(BaseModel):
    type: str
    items: GeminiSchemaProperty | None = None
    properties: dict[str, GeminiSchemaProperty] | None = None
    required: list[str] | None = None
    enum: list[str] | None = None


GeminiSchemaProperty.model_rebuild()


class GeminiGenerationConfig(BaseModel):
    responseMimeType: str
    responseSchema: GeminiSchemaProperty


class GeminiRequestPart(BaseModel):
    text: str


class GeminiRequestContent(BaseModel):
    parts: list[GeminiRequestPart]
    role: Literal["user", "model"] | None = None


class GeminiGenerateContentRequest(BaseModel):
    system_instruction: GeminiRequestContent | None = None
    contents: list[GeminiRequestContent]
    generationConfig: GeminiGenerationConfig


# --- Response models ---


class GeminiResponsePart(BaseModel):
    text: str


class GeminiResponseContent(BaseModel):
    parts: list[GeminiResponsePart] = Field(default_factory=list)
    role: str | None = None


class GeminiCandidate(BaseModel):
    content: GeminiResponseContent | None = None
    finishReason: str | None = None


class GeminiResponse(BaseModel):
    candidates: list[GeminiCandidate] = Field(default_factory=list)
