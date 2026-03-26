from typing import Literal

from pydantic import Field
from pydantic import HttpUrl
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from museflow import BASE_DIR
from museflow.infrastructure.types import LogHandler
from museflow.infrastructure.types import LogLevel


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MUSEFLOW_",
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

    LOG_LEVEL_API: LogLevel = "WARNING"
    LOG_HANDLERS_API: list[LogHandler] = ["console"]

    LOG_LEVEL_CLI: LogLevel = "WARNING"
    LOG_HANDLERS_CLI: list[LogHandler] = ["cli", "cli_alert"]

    HTTP_MAX_RETRIES: int = 5

    SYNC_SEMAPHORE_MAX_CONCURRENCY: int = 20

    RECONCILER_TRACK_MATCH_THRESHOLD: float = 80.0
    RECONCILER_TRACK_SCORE_MINIMUM: float = 60.0

    BACKEND_CORS_ALLOW_ORIGINS: list[HttpUrl | Literal["*"]] = Field(default_factory=list)
    BACKEND_CORS_ALLOW_METHODS: list[str] = Field(default=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"])
    BACKEND_CORS_ALLOW_HEADERS: list[str] = Field(
        default=[
            "Content-Type",
            "Set-Cookie",
            "Access-Control-Allow-Headers",
            "Authorization",
            "X-Requested-With",
            "Accept",
            "Origin",
        ]
    )
    BACKEND_CORS_ALLOW_CREDENTIALS: bool = False
    BACKEND_CORS_EXPOSE_HEADERS: list[str] = [
        "Content-Disposition",
        "X-Total-Count",
        "X-Response-Time",
    ]
    BACKEND_CORS_MAX_AGE: int = 600


app_settings = AppSettings()
