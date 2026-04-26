from enum import StrEnum
from pathlib import Path

from pydantic import Field, SecretStr, BaseModel

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
    service_name: str = "auth-service"
    app_port: int = 8001
    environment: EnvironmentEnum = EnvironmentEnum.DEV


class SecuritySettings(CustomBaseSettings):
    jwt_secret_key: SecretStr = SecretStr("FOAf+0nLwiRobdlA4/5gDOMttwaOU1f70c0I1zGba/M=")
    jwt_algorithm: str = "HS256"
    jwt_key_id: str = "primary"
    jwt_access_lifetime_minutes: int = 15
    jwt_refresh_lifetime_minutes: int = 60 * 24 * 30  # 30 days


class AuthenticationSettings(CustomBaseSettings):
    """Authentication configuration settings."""

    jwt: SecuritySettings = Field(default_factory=SecuritySettings)


class LoggerSettings(CustomBaseSettings):
    log_level: str = "DEBUG"
    app_logger_name: str = "app_logger"
    api_logger_name: str = "api_logger"


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


app_config: Configs = create_configs()
