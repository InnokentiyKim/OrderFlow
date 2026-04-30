import uuid
from datetime import datetime, UTC
from decimal import Decimal
from typing import Annotated, TypeAlias

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common import exceptions
from app.common.enums import OrderStatusEnum
from app.core.config import app_config
from app.schemas.result import CurrentUser
from app.integrations.dao.order import OrderDAO
from app.integrations.database import provide_db_session
from app.integrations.kafka import KafkaProducerClient
from app.models.orders import Order
from app.schemas.command import CreateOrderCommand
from app.schemas.event import OrderCreatedEvent
from app.schemas import result
from app.core.logger import get_logger


def _get_kafka_producer(request: Request) -> KafkaProducerClient:
    return request.app.state.kafka_producer


KafkaProducerDep: TypeAlias = Annotated[
    KafkaProducerClient, Depends(_get_kafka_producer)
]


class OrderService:
    def __init__(
        self,
        session: AsyncSession,
        producer: KafkaProducerClient,
        dao: OrderDAO | None = None,
    ) -> None:
        self._session = session
        self._producer = producer
        self._dao = dao or OrderDAO()
        self._logger = get_logger("OrderService")

    async def create_order(self, cmd: CreateOrderCommand) -> result.CreateOrderResult:
        """Create a new order in the system."""
        saga_id = uuid.uuid4()
        total_amount: Decimal = cmd.total_amount
        items_list = list(cmd.items)

        order = Order(
            user_id=cmd.user_id,
            status=OrderStatusEnum.PENDING,
            items=items_list,
            total_amount=total_amount,
            currency=cmd.currency,
            saga_id=saga_id,
        )

        # The session already has an open RLS-aware transaction
        await self._dao.create_order(self._session, order)
        await self._session.flush()
        await self._logger.ainfo(
            "Created new order",
            order_id=order.id,
            user_id=order.user_id,
            saga_id=saga_id,
        )

        # After the savepoint is released (data visible in the outer txn) publish to Kafka.
        # If Kafka is down we log and continue — the order is already durably persisted in the DB.
        event = OrderCreatedEvent(
            event_id=uuid.uuid4(),
            saga_id=saga_id,
            order_id=order.id,
            user_id=order.user_id,
            items=order.items,
            total_amount=order.total_amount,
            timestamp=datetime.now(UTC),
        )
        await self._producer.send(
            topic=app_config.broker.kafka_topic_order_events,
            value=event.model_dump(mode="json"),
            key=str(order.id),
        )
        await self._logger.ainfo(
            "Published order.created event to Kafka",
            order_id=order.id,
            saga_id=saga_id,
            event_id=event.event_id,
        )

        return result.CreateOrderResult.from_model(order)

    async def get_orders(
        self, current_user: CurrentUser
    ) -> list[result.GetOrderResult]:
        """Fetch all orders visible to the current user based on RLS policies."""
        orders = await self._dao.get_orders(self._session)
        await self._logger.ainfo(
            "Fetched orders for user", user_id=current_user.user_id
        )
        return [result.GetOrderResult.from_model(o) for o in orders]

    async def get_order(
        self, order_id: uuid.UUID, current_user: CurrentUser
    ) -> result.GetOrderResult:
        """Fetch a specific order by its ID, ensuring the current user has access based on RLS policies."""
        order = await self._dao.get_order_by_id(self._session, order_id)
        if order is None:
            raise exceptions.ItemNotFoundError(message="Order not found")

        await self._logger.ainfo(
            "Fetched order", order_id=order_id, user_id=current_user.user_id
        )
        return result.GetOrderResult.from_model(order)

    async def cancel_order(
        self, order_id: uuid.UUID, current_user: CurrentUser
    ) -> result.GetOrderResult:
        """
        Cancel an order if it's in PENDING status.

        This method acquires a row lock to ensure safe concurrent updates.
        It checks the current status of the order and only allows cancellation if it's still PENDING.
        If the order is already processed or cancelled, it raises an error.
        """
        order = await self._dao.get_order_by_id_for_update(self._session, order_id)

        if order is None:
            raise exceptions.ItemNotFoundError(message="Order not found")

        if order.status != OrderStatusEnum.PENDING:
            raise exceptions.OrderCancellationError(
                message=f"Cannot cancel order in status '{order.status}'"
            )

        order.set_status(OrderStatusEnum.CANCELLED)
        await self._session.flush()
        await self._logger.ainfo(
            "Cancelled order", order_id=order_id, user_id=current_user.user_id
        )

        return result.GetOrderResult.from_model(order)


def _build_order_service(
    session: AsyncSession = Depends(provide_db_session),
    producer: KafkaProducerClient = Depends(_get_kafka_producer),
) -> OrderService:
    return OrderService(session=session, producer=producer)


OrderServiceDependency: TypeAlias = Annotated[
    OrderService, Depends(_build_order_service)
]
