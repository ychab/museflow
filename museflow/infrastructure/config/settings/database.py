from typing import Self

from pydantic import PostgresDsn
from pydantic import model_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from museflow import BASE_DIR


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Option 1: Provide complete URI only (production/CI)
    URI: PostgresDsn | None = None

    # Option 2: Provide individual components (development)
    HOST: str | None = None
    PORT: int | None = None
    USER: str | None = None
    PASSWORD: str | None = None
    PATH: str | None = None

    @model_validator(mode="after")
    def build_or_validate_uri(self) -> Self:
        if self.URI is not None:
            return self

        required_fields = {
            "HOST": self.HOST,
            "PORT": self.PORT,
            "USER": self.USER,
            "PASSWORD": self.PASSWORD,
            "PATH": self.PATH,
        }

        missing = [field_name for field_name, field_value in required_fields.items() if field_value is None]
        if missing:
            raise ValueError(
                f"DATABASE_URI not provided. The following component fields are required: {', '.join(missing)}"
            )

        self.URI = PostgresDsn.build(
            scheme="postgresql+asyncpg",
            host=self.HOST,
            port=self.PORT,
            username=self.USER,
            password=self.PASSWORD,
            path=self.PATH,
        )

        return self


database_settings = DatabaseSettings()
