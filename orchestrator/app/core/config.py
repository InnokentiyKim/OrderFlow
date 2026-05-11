from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr, BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class EnvironmentEnum(StrEnum):
    DEV = "dev"
    STAGE = "stage"
    PROD = "prod"


class CustomBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class GeneralSettings(CustomBaseSettings):
    service_version: str = "0.0.1"
    service_name: str = "orchestrator"
    environment: EnvironmentEnum = EnvironmentEnum.DEV


class LoggerSettings(CustomBaseSettings):
    log_level: str = "DEBUG"
    app_logger_name: str = "app_logger"


class RetrySettings(CustomBaseSettings):
    saga_max_retries: int = 3
    saga_retry_poll_interval: float = 1.0
    saga_retry_base_backoff: float = 2.0
    saga_retry_jitter: float = 0.2


class BrokerSettings(CustomBaseSettings):
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_acks: int = 1
    kafka_retries: int = 3
    kafka_enable_idempotence: bool = False
    kafka_auto_commit: bool = False

    @field_validator("kafka_acks", mode="before")
    @classmethod
    def _normalize_acks(cls, v: object) -> int | str:
        if isinstance(v, str):
            if v in ("0", "1", "-1"):
                return int(v)
            if v.lower() == "all":
                return "all"
            raise ValueError(
                f"Invalid kafka_acks value: {v!r}. Use 0, 1, -1, or 'all'."
            )
        return v

    # Consumer
    kafka_consumer_group: str = "orchestrator"
    kafka_auto_offset_reset: str = "earliest"

    # Topics
    kafka_topic_order_events: str = "order.events"
    kafka_topic_inventory_commands: str = "inventory.commands"
    kafka_topic_payment_commands: str = "payment.commands"
    kafka_topic_dlq: str = "order.dlq"

    @model_validator(mode="after")
    def _check_idempotence_requires_acks_all(self) -> "BrokerSettings":
        if self.kafka_enable_idempotence and self.kafka_acks != "all":
            raise ValueError(
                "kafka_enable_idempotence=True requires kafka_acks='all', "
                f"got kafka_acks={self.kafka_acks!r}"
            )
        return self


class SqlEngineConfig(BaseModel):
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


class SqlSessionConfig(BaseModel):
    expire_on_commit: bool = False


class DatabaseSettings(CustomBaseSettings):
    postgres_user: str = "postgres"
    postgres_password: SecretStr = SecretStr("postgres")
    postgres_host: str = "localhost"
    postgres_port: str = "5432"
    postgres_db: str = "postgres"

    engine: SqlEngineConfig = Field(default_factory=SqlEngineConfig)
    session: SqlSessionConfig = Field(default_factory=SqlSessionConfig)

    @property
    def db_url(self) -> str:
        db_params = {
            "user": self.postgres_user,
            "password": self.postgres_password.get_secret_value(),
            "host": self.postgres_host,
            "port": self.postgres_port,
            "db": self.postgres_db,
        }
        return "postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}".format(
            **db_params
        )


class Configs(BaseSettings):
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    logger: LoggerSettings = Field(default_factory=LoggerSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    retry: RetrySettings = Field(default_factory=RetrySettings)


def create_configs() -> Configs:
    return Configs()


app_config: Configs = create_configs()
