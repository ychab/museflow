from typing import Literal

from pydantic import EmailStr
from pydantic import Field
from pydantic import HttpUrl
from pydantic import SecretStr
from pydantic import field_validator
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

    CLI_DEFAULT_EMAIL: EmailStr | None = None

    LOCALE: str = Field(default="en-US", pattern=r"^[a-z]{2}-[A-Z]{2}$")

    SECRET_KEY: SecretStr = Field(..., min_length=32)

    API_V1_PREFIX: str = "/api/v1"

    ACCESS_TOKEN_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    LOG_LEVEL_API: LogLevel = "WARNING"
    LOG_HANDLERS_API: list[LogHandler] = ["console"]

    LOG_LEVEL_CLI: LogLevel = "WARNING"
    LOG_HANDLERS_CLI: list[LogHandler] = ["console"]

    LOG_LEVEL_THIRD_PARTY: LogLevel = "WARNING"

    HTTP_MAX_RETRIES: int = 5

    RECONCILER_MATCH_THRESHOLD: float = 80.0

    TASTE_PROFILE_BUILD_THROTTLING_SLEEP_SECONDS: float = 0.0

    # About 30% of the advisor suggestions are lost to reconciliation and known tracks: ask for more than the target.
    DISCOVERY_ADVISOR_LIMIT_RATIO: float = 1.5
    DISCOVERY_RECONCILER_LIMIT: int = 10
    DISCOVERY_MAX_ATTEMPTS: int = 3
    DISCOVERY_MAX_TRACKS_PER_ARTIST: int = 3
    DISCOVERY_SCORE_BAND_WIDTH: float = 0.05
    DISCOVERY_BLACKLIST_SCORE_THRESHOLD: int = 3
    DISCOVERY_LIKED_SCORE_THRESHOLD: int = 7
    DISCOVERY_LIKED_TRACKS_LIMIT: int = 200  # 200 is a quality cap, not a technical constraint (higher is noise)
    DISCOVERY_DISLIKED_SCORE_THRESHOLD: int = 2
    DISCOVERY_DISLIKED_TRACKS_LIMIT: int = 50
    DISCOVERY_TOP_PLAYED_TRACKS_LIMIT: int = 100  # 0 sends none
    DISCOVERY_TOP_ARTISTS_LIMIT: int = 100  # 0 sends none

    STATS_BAYESIAN_CONFIDENCE: int = 5

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

    @field_validator("CLI_DEFAULT_EMAIL", mode="before")
    @classmethod
    def empty_cli_default_email_is_none(cls, value: str | None) -> str | None:
        # An empty MUSEFLOW_CLI_DEFAULT_EMAIL= reads as "not set", not as an invalid email. Not env_ignore_empty: an
        # empty variable would no longer override .env, and an empty value could no longer be set on purpose.
        return value or None


app_settings = AppSettings()
