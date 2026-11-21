from typing import Self

from pydantic import AmqpDsn
from pydantic import SecretStr
from pydantic import model_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from museflow import BASE_DIR


class BrokerSettings(BaseSettings):
    """The RabbitMQ the tasks are published to and the workers consume them from.

    Either a complete URL (`BROKER_URL`, as the containers get it), or its components (host, port, user, password),
    from which the URL is built on the default virtual host.
    """

    model_config = SettingsConfigDict(
        env_prefix="BROKER_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Option 1: the complete URL, its password included: amqp://user:password@host:5672/vhost
    URL: SecretStr | None = None

    # Option 2: its components (development)
    HOST: str | None = None
    PORT: int | None = None
    USER: str | None = None
    PASSWORD: str | None = None

    @model_validator(mode="after")
    def build_or_validate_url(self) -> Self:
        if self.URL is not None:
            return self

        if self.HOST is None or self.PORT is None or self.USER is None or self.PASSWORD is None:
            required_fields = {"HOST": self.HOST, "PORT": self.PORT, "USER": self.USER, "PASSWORD": self.PASSWORD}
            missing = [field_name for field_name, field_value in required_fields.items() if field_value is None]
            raise ValueError(
                f"BROKER_URL not provided. The following component fields are required: {', '.join(missing)}"
            )

        url = AmqpDsn.build(
            scheme="amqp",
            host=self.HOST,
            port=self.PORT,
            username=self.USER,
            password=self.PASSWORD,
            # The default virtual host, "/"
            path="/",
        )
        self.URL = SecretStr(str(url))

        return self


broker_settings = BrokerSettings()
