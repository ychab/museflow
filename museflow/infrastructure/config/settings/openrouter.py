from typing import Annotated

from pydantic import BaseModel
from pydantic import Field
from pydantic import HttpUrl
from pydantic import SecretStr
from pydantic import UrlConstraints
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from museflow import BASE_DIR
from museflow.infrastructure.types import ReasoningEffort


class LLMSettings(BaseModel):
    """Model tuning for one LLM step; `None` leaves the provider's default."""

    MODEL: str
    MAX_TOKENS: int | None = Field(default=None, gt=0)
    REASONING_EFFORT: ReasoningEffort | None = None
    TEMPERATURE: float | None = Field(default=None, ge=0.0, le=2.0)
    FALLBACK_MODELS: list[str] = Field(default_factory=list)

    def with_model(self, model: str | None) -> LLMSettings:
        """Returns these settings with `model` in place of `MODEL`, unchanged when `model` is None (a CLI override)."""
        return self.model_copy(update={"MODEL": model}) if model else self


class OpenRouterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENROUTER_",
        env_nested_delimiter="__",  # OPENROUTER_ENRICHER__MODEL=...
        nested_model_default_partial_update=True,  # a single nested override keeps the step's other defaults
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    API_KEY: SecretStr

    # HTTPS only: every request carries the API key and the user's listening history
    BASE_URL: Annotated[HttpUrl, UrlConstraints(allowed_schemes=["https"])] = Field(
        default=HttpUrl("https://openrouter.ai/api/v1/")
    )

    ADVISOR: LLMSettings = LLMSettings(MODEL="google/gemini-2.5-flash")

    ENRICHER: LLMSettings = LLMSettings(MODEL="google/gemini-2.5-flash-lite")

    PROFILER_SEGMENT: LLMSettings = LLMSettings(MODEL="google/gemini-2.5-flash-lite")
    PROFILER_MERGE: LLMSettings = LLMSettings(MODEL="google/gemini-3.5-flash")
    PROFILER_REFLECT: LLMSettings = LLMSettings(MODEL="google/gemini-3.1-pro-preview")

    # Zero Data Retention: only route to provider endpoints that neither store prompts and completions nor train on
    # them, since our prompts carry the user's listening history. Narrows the models available; `data_collection:
    # deny` is sent either way.
    ZDR: bool = True

    HTTP_TIMEOUT: float = 180.0
    HTTP_MAX_RETRIES: int = 10
    HTTP_MAX_RETRY_WAIT: int = 120

    VALIDATION_MAX_RETRIES: int = Field(default=2, ge=0)


openrouter_settings = OpenRouterSettings()
