from pydantic import Field
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from spotifagent import BASE_DIR
from spotifagent.infrastructure.types import LogHandler
from spotifagent.infrastructure.types import LogLevel


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPOTIFAGENT_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DEBUG: bool = False

    LOCALE: str = Field(default="en-US", pattern=r"^[a-z]{2}-[A-Z]{2}$")

    SECRET_KEY: str = Field(..., min_length=32)

    API_V1_PREFIX: str = "/api/v1"

    ACCESS_TOKEN_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    LOG_LEVEL: LogLevel = "INFO"
    LOG_HANDLERS: list[LogHandler] = ["console"]


app_settings = AppSettings()
