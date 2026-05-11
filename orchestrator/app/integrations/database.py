from typing import AsyncIterable

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import app_config

engine: AsyncEngine = create_async_engine(
    app_config.database.db_url, **app_config.database.engine.model_dump()
)

_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=app_config.database.session.expire_on_commit,
)


async def provide_db_session() -> AsyncIterable[AsyncSession]:
    async with _session_factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return _session_factory
