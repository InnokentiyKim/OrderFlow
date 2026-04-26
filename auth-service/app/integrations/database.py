from typing import AsyncIterable, TypeAlias, Annotated

from fastapi import Depends

from app.core.config import app_config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


engine: AsyncEngine = create_async_engine(
    app_config.database.db_url, **app_config.database.engine.model_dump()
)


async def provide_db_session() -> AsyncIterable[AsyncSession]:
    session_config = app_config.database.session

    async with async_sessionmaker(
        engine, expire_on_commit=session_config.expire_on_commit
    )() as session:
        yield session


SessionDependency: TypeAlias = Annotated[AsyncSession, Depends(provide_db_session)]  # type: ignore
