import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orders import Order


class OrderDAO:
    """Data-access layer.

    Row Level Security is enforced by PostgreSQL itself — the database
    physically filters rows according to the active RLS policies before
    returning them to the application.  No Python ownership checks are
    needed here; they would be redundant and error-prone.

    How it works:
        RLSContextMiddleware  →  sets ContextVars (user_id, pg_role)
        provide_db_session    →  SET LOCAL ROLE <pg_role>
                                 SET LOCAL app.current_user_id = '<uuid>'
        PostgreSQL            →  applies matching USING / WITH CHECK policy
        OrderDAO              →  just writes the SQL intent, DB does the rest
    """

    @staticmethod
    async def create_order(session: AsyncSession, order: Order) -> Order:
        session.add(order)
        await session.flush()
        return order

    @staticmethod
    async def get_order_by_id(
        session: AsyncSession,
        order_id: uuid.UUID,
    ) -> Order | None:
        """SELECT single order.

        RLS policy for app_customer automatically adds:
            AND user_id = current_setting('app.current_user_id')::uuid
        at the PostgreSQL level.  app_admin gets USING(true) — no filter.
        """
        stmt = select(Order).where(Order.id == order_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_order_by_id_for_update(
        session: AsyncSession,
        order_id: uuid.UUID,
    ) -> Order | None:
        """SELECT FOR UPDATE — row lock + RLS in one shot.

        PostgreSQL evaluates the USING clause *before* acquiring the lock,
        so a foreign row is never locked: it simply isn't visible to the query.
        """
        stmt = select(Order).where(Order.id == order_id).with_for_update()
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_orders(session: AsyncSession) -> Sequence[Order]:
        """Return visible orders.

        app_customer → DB returns only rows where user_id matches the GUC.
        app_admin    → DB returns all rows (USING(true) policy).
        """
        stmt = select(Order)
        result = await session.execute(stmt)
        return result.scalars().all()
