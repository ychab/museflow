from pydantic import AnyUrl
from pydantic import Field
from pydantic import HttpUrl
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from museflow import BASE_DIR


class SpotifySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPOTIFY_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    CLIENT_ID: str
    CLIENT_SECRET: SecretStr

    BASE_URL: HttpUrl = Field(default=HttpUrl("https://api.spotify.com/v1"))
    AUTH_ENDPOINT: HttpUrl = Field(default=HttpUrl("https://accounts.spotify.com/authorize"))
    TOKEN_ENDPOINT: HttpUrl = Field(default=HttpUrl("https://accounts.spotify.com/api/token"))

    # The redirect URIs an API client may ask for (its web page, its app scheme), each registered with Spotify: the
    # provider sends the browser back to the client, which hands the code to the API. Empty: the API connects no one.
    REDIRECT_URIS: list[AnyUrl] = Field(default_factory=list)

    HTTP_TIMEOUT: float = 30.0
    HTTP_MAX_RETRIES: int = 5
    HTTP_MAX_RETRY_WAIT: int = 60
    # Searches run at the same time for one artist's catalogue, one per release year range: few enough for the
    # rate limit, whose 429 is retried after its Retry-After
    SEARCH_CONCURRENCY: int = Field(default=4, ge=1)

    TOKEN_BUFFER_SECONDS: int = 60 * 5


spotify_settings = SpotifySettings()
