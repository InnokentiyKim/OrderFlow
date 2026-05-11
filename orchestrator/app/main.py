import asyncio
import signal

import structlog

from app.core.config import app_config
from app.core.logger import setup_logging
from app.consumer.runner import run_consumer
from app.consumer.dlq_reader import run_dlq_reader
from app.integrations.database import engine, get_session_factory
from app.integrations.kafka_producer import KafkaProducerClient
from app.saga.retry_worker import run_retry_worker, recover_stuck_sagas

setup_logging(app_config)
logger = structlog.get_logger(__name__)


async def _main() -> None:
    producer = KafkaProducerClient()
    await producer.start()

    session_factory = get_session_factory()

    # Recover any sagas that were left mid-flight before the crash/restart.
    # Must run before the consumer and retry worker start to avoid races.
    await recover_stuck_sagas(session_factory)

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _shutdown(*_args: object) -> None:
        if not shutdown_event.is_set():
            logger.info("shutdown signal received")
            shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown, None)

    consumer_task = asyncio.create_task(run_consumer(producer, shutdown_event))
    retry_poll_interval = app_config.retry.saga_retry_poll_interval
    retry_task = asyncio.create_task(
        run_retry_worker(
            producer,
            session_factory,
            poll_interval=retry_poll_interval,
            shutdown_event=shutdown_event,
        )
    )
    dlq_task = asyncio.create_task(run_dlq_reader(shutdown_event))

    await asyncio.gather(consumer_task, retry_task, dlq_task, return_exceptions=True)

    # Shutdown order: consumers already stopped → producer → DB
    await producer.stop()
    await logger.ainfo("producer stopped")

    await engine.dispose()
    await logger.ainfo("db pool closed")


if __name__ == "__main__":
    asyncio.run(_main())
