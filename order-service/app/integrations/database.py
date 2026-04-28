from typing import AsyncIterable, TypeAlias, Annotated

from fastapi import Depends
from sqlalchemy import text

from app.core.config import app_config
from app.integrations.rls_context import rls_user_id, rls_db_role
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class RLSAsyncSession(AsyncSession):
    """Custom AsyncSession that injects RLS context on transaction begin."""

    async def inject_rls(self) -> None:
        """Read RLS identity from ContextVars and inject SET LOCAL into the transaction."""
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
    """FastAPI dependency that provides an AsyncSession with RLS context injected."""
    async with _session_factory() as session:
        async with session.begin():
            await session.inject_rls()
            yield session


SessionDependency: TypeAlias = Annotated[AsyncSession, Depends(provide_db_session)]  # type: ignore
