from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from museflow import BASE_DIR


class BrokerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BROKER_",
        env_file=[BASE_DIR / ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # The RabbitMQ the tasks are published to and the workers consume them from, its password included:
    # amqp://user:password@host:5672/vhost
    URL: SecretStr


broker_settings = BrokerSettings()
