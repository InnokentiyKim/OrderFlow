from enum import StrEnum
from pathlib import Path
from typing import TypeAlias

from fastapi import Depends
from pydantic import Field, SecretStr, BaseModel, field_validator, model_validator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.sql.annotation import Annotated


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
    service_name: str = "payment-service"
    app_port: int = 8002
    environment: EnvironmentEnum = EnvironmentEnum.DEV


class LoggerSettings(CustomBaseSettings):
    log_level: str = "DEBUG"
    app_logger_name: str = "app_logger"
    api_logger_name: str = "api_logger"


class SecuritySettings(CustomBaseSettings):
    jwt_secret_key: SecretStr = SecretStr(
        "FOAf+0nLwiRobdlA4/5gDOMttwaOU1f70c0I1zGba/M="
    )
    jwt_algorithm: str = "HS256"


class AuthenticationSettings(CustomBaseSettings):
    """Authentication configuration settings."""

    jwt: SecuritySettings = Field(default_factory=SecuritySettings)


class BrokerSettings(CustomBaseSettings):
    kafka_bootstrap_servers: str = "payment-kafka:9092"
    kafka_acks: int | str = 1  # 0, 1, or "all" (-1)
    kafka_retries: int = 3
    kafka_enable_idempotence: bool = False
    kafka_topic_order_events: str = "order.events"

    @field_validator("kafka_acks", mode="before")
    @classmethod
    def _normalize_acks(cls, v: object) -> int | str:
        """Env vars are always strings; convert '0'/'1'/'-1' to int,
        keep 'all' as-is. aiokafka accepts int(0), int(1) or str('all')."""
        if isinstance(v, str):
            if v in ("0", "1", "-1"):
                return int(v)
            if v.lower() == "all":
                return "all"
            raise ValueError(
                f"Invalid kafka_acks value: {v!r}. Use 0, 1, -1, or 'all'."
            )
        return v

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
        """
        Constructs the full database connection URL for SQLAlchemy with the asyncpg driver.

        Returns:
            str: A fully formatted database URL string
        """
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
    auth: AuthenticationSettings = Field(default_factory=AuthenticationSettings)
    logger: LoggerSettings = Field(default_factory=LoggerSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)


def create_configs() -> Configs:
    """
    Creates and returns a Configs instance.

    This function creates an instance of the `Configs` class, which aggregates
    all configuration settings required by the application

    Returns:
        Configs: The configuration settings.
    """
    return Configs()


ConfigDepends: TypeAlias = Annotated[Configs, Depends(create_configs)]  # type: ignore

app_config: Configs = create_configs()
