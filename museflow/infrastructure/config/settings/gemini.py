from pydantic import Field
from pydantic import HttpUrl
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from museflow import BASE_DIR
from museflow.infrastructure.adapters.common.gemini.types import GeminiModel


class GeminiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GEMINI_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    API_KEY: str

    BASE_URL: HttpUrl = Field(default=HttpUrl("https://generativelanguage.googleapis.com/v1beta/"))

    ADVISOR_MODEL: GeminiModel = GeminiModel.FLASH_2_5
    PROFILER_SEGMENT_MODEL: GeminiModel = GeminiModel.FLASH_3_0_PREVIEW
    PROFILER_MERGE_MODEL: GeminiModel = GeminiModel.PRO_3_1_PREVIEW
    PROFILER_REFLECT_MODEL: GeminiModel = GeminiModel.FLASH_2_5

    HTTP_TIMEOUT: float = 30.0
    HTTP_MAX_RETRIES: int = 5
    HTTP_MAX_RETRY_WAIT: int = 60


gemini_settings = GeminiSettings()
