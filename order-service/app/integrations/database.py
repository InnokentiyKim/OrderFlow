from typing import AsyncIterable, TypeAlias

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.sql.annotation import Annotated

from app.core.config import app_config
from app.integrations.rls_context import rls_user_id, rls_db_role
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class RLSAsyncSession(AsyncSession):
    """AsyncSession that automatically injects the RLS context on every BEGIN.

    Overrides ``begin()`` so that immediately after PostgreSQL receives
    ``BEGIN``, two ``SET LOCAL`` statements are issued:

        SET LOCAL ROLE <pg_role>
        SET LOCAL app.current_user_id = '<uuid>'

    ``SET LOCAL`` is scoped to the current transaction — when the transaction
    ends (COMMIT / ROLLBACK) both settings are reset automatically, so the
    connection is returned to the pool in a clean state.

    Because the injection happens inside ``begin()`` itself, every call site
    — the session provider, services, background tasks — gets RLS for free
    without any extra boilerplate.
    """

    async def _inject_rls(self) -> None:
        user_id = rls_user_id.get()
        role = rls_db_role.get()
        if user_id is not None and role is not None:
            # role comes from _ROLE_MAP in RLSContextMiddleware — not user input.
            await self.execute(text(f"SET LOCAL ROLE {role}"))  # noqa: S608
            await self.execute(
                text(f"SET LOCAL app.current_user_id = '{user_id}'")  # noqa: S608
            )


engine: AsyncEngine = create_async_engine(
    app_config.database.db_url, **app_config.database.engine.model_dump()
)

_session_factory = async_sessionmaker(
    engine,
    class_=RLSAsyncSession,  # ← custom session class
    expire_on_commit=app_config.database.session.expire_on_commit,
)


async def provide_db_session() -> AsyncIterable[AsyncSession]:
    """Open one RLS-aware transaction for the lifetime of an HTTP request.

    Flow
    ────
    1. Create an ``RLSAsyncSession`` from the pool.
    2. Call ``session.begin()`` → our override fires → BEGIN sent to PostgreSQL
       → SET LOCAL ROLE + SET LOCAL app.current_user_id injected.
    3. Yield the session.  Services use it directly — no ``begin_nested()``
       needed, because there is already one active transaction with the RLS
       context baked in.
    4. COMMIT on clean exit, ROLLBACK on exception.  SET LOCAL resets
       automatically — connection returns to the pool clean.
    """
    async with _session_factory() as session:
        async with session.begin():
            await session._inject_rls()
            yield session


SessionDependency: TypeAlias = Annotated[AsyncSession, Depends(provide_db_session)]  # type: ignore
