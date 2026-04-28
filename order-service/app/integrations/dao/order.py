import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orders import Order


class OrderDAO:
    """
    Data Access Object for Order model.

    This class provides methods to interact with the orders table in the database.
    It includes methods to create a new order, retrieve an order by its ID (with or without a row lock),
    and retrieve all orders visible to the current user based on RLS policies.
    """

    @staticmethod
    async def create_order(session: AsyncSession, order: Order) -> Order:
        """Insert a new order into the database."""
        session.add(order)
        await session.flush()
        return order

    @staticmethod
    async def get_order_by_id(
        session: AsyncSession,
        order_id: uuid.UUID,
    ) -> Order | None:
        """Retrieve an order by its ID without acquiring a row lock."""
        stmt = select(Order).where(Order.id == order_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_order_by_id_for_update(
        session: AsyncSession,
        order_id: uuid.UUID,
    ) -> Order | None:
        """Retrieve an order by its ID and acquire a row lock for update."""
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_orders(session: AsyncSession) -> Sequence[Order]:
        """Retrieve all orders visible to the current user based on RLS policies."""
        stmt = select(Order)
        result = await session.execute(stmt)
        return result.scalars().all()
