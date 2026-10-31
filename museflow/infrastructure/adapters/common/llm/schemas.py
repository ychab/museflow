from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from museflow.infrastructure.adapters.common.llm.json_schema import JsonSchemaProperty
from museflow.infrastructure.types import ReasoningEffort

# --- Request models ---


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class JsonSchemaFormat(BaseModel):
    name: str
    strict: bool = True
    schema_: JsonSchemaProperty = Field(serialization_alias="schema")


class ResponseFormat(BaseModel):
    type: Literal["json_schema"] = "json_schema"
    json_schema: JsonSchemaFormat


class ReasoningConfig(BaseModel):
    effort: ReasoningEffort


class ProviderPreferences(BaseModel):
    require_parameters: bool = True  # only route to endpoints supporting every parameter sent (response_format)
    zdr: bool
    data_collection: Literal["allow", "deny"] = "deny"


class ChatCompletionRequest(BaseModel):
    model: str
    models: list[str] | None = None  # fallback chain, in priority order
    messages: list[ChatMessage]
    response_format: ResponseFormat
    max_tokens: int | None = None
    temperature: float | None = None
    reasoning: ReasoningConfig | None = None
    provider: ProviderPreferences


# --- Response models ---


class ChatResponseMessage(BaseModel):
    role: str | None = None
    content: str | None = None
    refusal: str | None = None


class ChatChoice(BaseModel):
    message: ChatResponseMessage | None = None
    finish_reason: str | None = None


class ChatCompletionError(BaseModel):
    code: int | str | None = None
    message: str = ""


class ChatCompletionResponse(BaseModel):
    model: str | None = None  # the model actually used, which differs from the requested one on fallback
    choices: list[ChatChoice] = Field(default_factory=list)
    error: ChatCompletionError | None = None


# --- Model catalog ---


class CatalogModel(BaseModel):
    id: str
    supported_parameters: list[str] = Field(default_factory=list)  # union over the model's provider endpoints


class ModelCatalogResponse(BaseModel):
    data: list[CatalogModel]
