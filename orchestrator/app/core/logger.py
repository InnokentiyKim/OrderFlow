import logging
import re

import structlog
from structlog.types import Processor

from app.core.config import Configs, EnvironmentEnum


def _strip_ansi(_, __, event_dict):
    """Remove ANSI escape codes from log messages."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    if "event" in event_dict:
        event_dict["event"] = ansi_escape.sub("", event_dict["event"])

    event_dict.pop("color_message", None)
    return event_dict


def build_shared_processors() -> list[Processor]:
    """
    Build a list of shared structlog processors for logging.

    Returns:
        list[Processor]: A list of structlog processors.
    """
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.ExtraAdder(),
        structlog.processors.StackInfoRenderer(),
        _strip_ansi,
    ]

    return processors


def setup_logging(config: Configs) -> None:
    """
    Set up structlog logging configuration based on the provided settings.

    Args:
        config (Configs): The application configuration.

    Returns:
        None
    """
    shared_processors = build_shared_processors()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # The ProcessorFormatter allows us to:
    #  - run a chain of processors on log records from Python's logging
    #  - then run a final set of processors (including the final renderer)
    formatter = structlog.stdlib.ProcessorFormatter(
        # These run ONLY on `logging` entries that do NOT originate within the structlog.
        foreign_pre_chain=shared_processors,
        processors=[
            # Remove internal structlog metadata so it doesn't show up in the final log.
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # Choose the final renderer based on config (JSON or console).
            (
                structlog.dev.ConsoleRenderer()
                if config.general.environment == EnvironmentEnum.DEV
                else structlog.processors.JSONRenderer()
            ),
        ],
    )

    # Create a default StreamHandler to output logs to sys.stderr (or stdout).
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    # Attach this handler to the root logger. This ensures all logs end up going through the structlog.
    root_logger = logging.getLogger()
    root_logger.addHandler(stream_handler)
    # Set the log level (e.g., INFO, DEBUG, etc.) based on user configs.
    root_logger.setLevel(config.logger.log_level.upper())

    # For Uvicorn's primary loggers, clear their default handlers and propagate to root.
    # This ensures that "uvicorn", "uvicorn.error" and FS logs go through structlog.
    for log_type in (
        "uvicorn",
        "uvicorn.error",
    ):
        logging.getLogger(log_type).handlers.clear()
        logging.getLogger(log_type).propagate = True

    # Avoid duplicate or redundant logs re-emitted by Uvicorn access logger.
    for log_type in (
        "uvicorn.access",
        "asyncio",
        "urllib3",
        "httpcore",
    ):
        logging.getLogger(log_type).handlers.clear()
        logging.getLogger(log_type).propagate = False
