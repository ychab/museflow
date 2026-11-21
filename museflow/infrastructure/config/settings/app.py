from pathlib import Path
from typing import Annotated
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
    # Port of the redirect URI of `provider connect`, see `cli_oauth_redirect_uri`: one where nothing listens, so that
    # the page doesn't load and no service (the API on 8000) receives the code.
    CLI_OAUTH_REDIRECT_PORT: int = Field(default=65535, ge=1, le=65535)

    LOCALE: str = Field(default="en-US", pattern=r"^[a-z]{2}-[A-Z]{2}$")

    # The JWT access tokens of the API. The key signs them: whoever holds it can sign in as any user
    JWT_SIGNING_KEY: SecretStr = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30

    # Encrypts the provider OAuth tokens at rest. To rotate it, move it to the fallbacks, set a new one, run
    # `provider reencrypt-tokens`, then drop the fallback: see docs/technical/token-encryption.md
    PROVIDER_TOKEN_ENCRYPTION_KEY: SecretStr = Field(..., min_length=32)
    # Former keys, which still decrypt the tokens they encrypted until these are encrypted again
    PROVIDER_TOKEN_ENCRYPTION_KEY_FALLBACKS: list[Annotated[SecretStr, Field(min_length=32)]] = Field(
        default_factory=list
    )

    API_V1_PREFIX: str = "/api/v1"

    LOG_LEVEL_API: LogLevel = "WARNING"
    LOG_HANDLERS_API: list[LogHandler] = ["console"]

    LOG_LEVEL_CLI: LogLevel = "WARNING"
    LOG_HANDLERS_CLI: list[LogHandler] = ["console"]

    LOG_LEVEL_THIRD_PARTY: LogLevel = "WARNING"

    HTTP_MAX_RETRIES: int = 5

    # Root of the files kept between their upload and their processing (streaming history exports), one directory
    # per user: a volume shared by the API and the workers once deployed.
    FILE_STORAGE_DIR: Path = BASE_DIR / ".storage"

    TASTE_PROFILE_BUILD_THROTTLING_SLEEP_SECONDS: float = 0.0
    # How long a build holds its profile without saving a checkpoint; longer than its slowest period.
    TASTE_PROFILE_BUILD_LEASE_MINUTES: int = Field(default=15, ge=1)

    # Artists asked and tracks picked per attempt, against the playlist size: the per-artist cap and the advisor
    # returning fewer picks than asked both eat into them.
    DISCOVERY_ADVISOR_LIMIT_RATIO: float = 1.5
    DISCOVERY_ARTIST_TRACKS_PAGES: int = Field(default=2, ge=1)  # pages of 10 search results per suggested artist
    # Per query of the catalogue search (one per release year range on Spotify), for an artist whose own tracks the
    # request asks for: the plain search's first pages hold their best-known tracks (#203)
    DISCOVERY_REQUESTED_ARTIST_TRACKS_PAGES: int = Field(default=10, ge=1)
    DISCOVERY_MAX_ATTEMPTS: int = 3
    DISCOVERY_MAX_TRACKS_PER_ARTIST: int = 3
    DISCOVERY_BLACKLIST_SCORE_THRESHOLD: int = 3
    DISCOVERY_LIKED_SCORE_THRESHOLD: int = 7
    DISCOVERY_LIKED_TRACKS_LIMIT: int = 200  # 200 is a quality cap, not a technical constraint (higher is noise)
    DISCOVERY_DISLIKED_SCORE_THRESHOLD: int = 2
    DISCOVERY_DISLIKED_TRACKS_LIMIT: int = 50
    DISCOVERY_COVERED_ARTISTS_LIMIT: int = 100  # 0 sends none

    # `playlist explore`: the favourites drawn from (ratings first, then plays), then searched per round; 5 per round
    # fill 10 tracks at 3 per artist, with room for those whose unknown tracks don't fit. The picks, the catalogue
    # search, the rounds and the per-artist cap follow the DISCOVERY_ settings above.
    EXPLORE_ARTISTS_LIMIT: int = Field(default=20, ge=1)
    EXPLORE_ARTISTS_PER_ATTEMPT: int = Field(default=5, ge=1)
    # Artists whose catalogue is searched at the same time, each with SPOTIFY_SEARCH_CONCURRENCY queries in flight:
    # 4 artists (16 queries) met 22 to 28 retried 429s a run (#208); 1 keeps the 4 queries of a single artist's search
    EXPLORE_ARTISTS_CONCURRENCY: int = Field(default=1, ge=1)

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

    @property
    def cli_oauth_redirect_uri(self) -> HttpUrl:
        """Where the provider sends the browser back after the consent of `provider connect`, registered with each
        provider.

        On the loopback address, so the code never leaves the machine running the command; nothing listens there: the
        user pastes the URL of that page into the terminal.
        """
        return HttpUrl(f"http://127.0.0.1:{self.CLI_OAUTH_REDIRECT_PORT}/cli/callback")


app_settings = AppSettings()
