from pydantic import Field
from pydantic import HttpUrl
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from spotifagent import BASE_DIR


class SpotifySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPOTIFY_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    CLIENT_ID: str
    CLIENT_SECRET: str

    REDIRECT_URI: HttpUrl = Field(default=HttpUrl("http://127.0.0.1:8000/api/v1/spotify/callback"))

    HTTP_TIMEOUT: float = 30.0

    TOKEN_BUFFER_SECONDS: int = 60 * 5


spotify_settings = SpotifySettings()
