import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import EventTypeEnum, SagaStateEnum
from app.core.config import app_config
from app.integrations.dao.saga import SagaStateDAO
from app.integrations.kafka_producer import KafkaProducerClient
from app.models.events import IncomingEvent
from app.models.saga_state import SagaState
from app.saga.handlers import (
    HandlerFunc,
    handle_order_created,
    handle_order_created_duplicate,
    handle_inventory_reserved,
    handle_payment_succeeded,
    handle_reservation_cancelled,
    handle_failure,
)

logger = structlog.get_logger(__name__)

DispatchKey = tuple[EventTypeEnum, SagaStateEnum | None]


def build_dispatcher() -> dict[DispatchKey, HandlerFunc]:
    """Builds the dispatcher mapping (event_type, saga_state) → handler function."""
    return {
        (EventTypeEnum.ORDER_CREATED, None): handle_order_created,
        (
            EventTypeEnum.ORDER_CREATED,
            SagaStateEnum.CREATED,
        ): handle_order_created_duplicate,
        (
            EventTypeEnum.INVENTORY_RESERVED,
            SagaStateEnum.INVENTORY_RESERVING,
        ): handle_inventory_reserved,
        (
            EventTypeEnum.INVENTORY_RESERVE_FAILED,
            SagaStateEnum.INVENTORY_RESERVING,
        ): handle_failure,
        (
            EventTypeEnum.PAYMENT_SUCCEEDED,
            SagaStateEnum.PAYMENT_CHARGING,
        ): handle_payment_succeeded,
        (EventTypeEnum.PAYMENT_FAILED, SagaStateEnum.PAYMENT_CHARGING): handle_failure,
        (
            EventTypeEnum.INVENTORY_RESERVATION_CANCELLED,
            SagaStateEnum.COMPENSATING_INVENTORY,
        ): handle_reservation_cancelled,
        (
            EventTypeEnum.INVENTORY_RESERVATION_CANCEL_FAILED,
            SagaStateEnum.COMPENSATING_INVENTORY,
        ): handle_failure,
    }


class SagaOrchestrator:
    def __init__(
        self,
        producer: KafkaProducerClient,
        dao: SagaStateDAO | None = None,
        dispatcher: dict[DispatchKey, HandlerFunc] | None = None,
    ) -> None:
        self._producer = producer
        self._dao = dao or SagaStateDAO()
        self._broker_cfg = app_config.broker
        self._retry_cfg = app_config.retry
        self._dispatcher: dict[DispatchKey, HandlerFunc] = (
            dispatcher or build_dispatcher()
        )

    async def handle_event(
        self,
        session: AsyncSession,
        event: IncomingEvent,
    ) -> None:
        """Main entry point for processing incoming events."""
        event_type = EventTypeEnum(event.event_type)
        saga_id = event.saga_id

        saga: SagaState | None = await self._dao.get_by_saga_id(session, saga_id)

        if saga is not None and saga.state.is_terminal:
            await logger.awarning(
                "Saga is in terminal state, ignoring event",
                event_type=event_type,
                current_state=saga.state,
                saga_id=str(saga_id),
            )
            return

        state: SagaStateEnum | None = saga.state if saga is not None else None
        key: DispatchKey = (event_type, state)
        handler: HandlerFunc | None = self._dispatcher.get(key)

        if handler is None:
            await logger.awarning(
                "No handler for (event_type, state), ignoring",
                event_type=event_type,
                current_state=state,
                saga_id=str(saga_id),
            )
            return

        await handler(
            session,
            saga,
            event,
            producer=self._producer,
            dao=self._dao,
            broker_cfg=self._broker_cfg,
            retry_cfg=self._retry_cfg,
        )
