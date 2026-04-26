from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.refresh_tokens import RefreshToken
from app.common import exceptions


class RefreshTokenDAO:
    @staticmethod
    async def add_refresh_token(session: AsyncSession, token: RefreshToken) -> None:
        """Add a new refresh token to the database."""
        session.add(token)
        try:
            await session.commit()
        except IntegrityError as err:
            await session.rollback()
            raise exceptions.ItemAlreadyExistsError("Token already exists") from err

    @staticmethod
    async def get_refresh_token(
        session: AsyncSession,
        hashed_refresh_token: str,
        user_id: UUID,
    ) -> RefreshToken | None:
        """Retrieve a refresh token by its hashed value and associated user ID."""
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash == hashed_refresh_token,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_users_refresh_tokens(
        session: AsyncSession,
        user_id: UUID,
    ) -> list[RefreshToken]:
        """Retrieve a refresh tokens by associated user ID."""
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked == False,  # noqa: E712
        )
        result = await session.execute(stmt)
        return list(result.scalars())

    @staticmethod
    async def invalidate_refresh_token(
        session: AsyncSession, token: RefreshToken
    ) -> None:
        """Invalidate a refresh token by setting its is_valid flag to False."""
        token.revoke()
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise exceptions.DatabaseError("Failed to invalidate token") from None

    @staticmethod
    async def update_refresh_token(
        session: AsyncSession, token: RefreshToken, **params: Any
    ) -> UUID:
        """Update an existing refresh token."""
        token_id = token.id
        stmt = update(RefreshToken).where(RefreshToken.id == token_id).values(**params)
        try:
            await session.execute(stmt)
            return token_id
        except IntegrityError:
            raise exceptions.DatabaseError("Failed to update token") from None
