from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_consumer_group: str = "inventory-service"
    kafka_input_topic: str = "inventory.commands"
    kafka_output_topic: str = "order.events"
    kafka_auto_offset_reset: str = "earliest"
    kafka_enable_auto_commit: bool = False

    redis_url: str = "redis://redis:6379/0"
    idempotency_ttl: int = 86400  # seconds

    database_url: str = "postgresql://postgres:postgres@stub-db:5432/postgres"

    log_level: str = "INFO"
    app_port: int = 8003
    app_host: str = "0.0.0.0"


settings = Settings()
