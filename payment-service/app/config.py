from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_consumer_group: str = "payment-service"
    kafka_input_topic: str = "payment.commands"
    kafka_output_topic: str = "order.events"
    kafka_auto_offset_reset: str = "earliest"
    kafka_enable_auto_commit: bool = False


    # Redis
    redis_url: str = "redis://redis:6379/1"
    idempotency_ttl: int = 86400

    # Database
    database_url: str = "postgresql://postgres:postgres@stub-db:5432/postgres"

    # App
    log_level: str = "INFO"
    app_port: int = 8004
    app_host: str = "0.0.0.0"

    # Business logic
    payment_success_probability: float = 0.7


settings = Settings()
