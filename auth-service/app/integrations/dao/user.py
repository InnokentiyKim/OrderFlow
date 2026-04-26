from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.users import User
from app.common import exceptions


class UserDAO:
    @staticmethod
    async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
        """Retrieve a user by their email address."""
        query = select(User).filter_by(email=email)
        row = await session.execute(query)
        return row.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
        """Retrieve a user by their unique identifier."""
        query = select(User).filter_by(id=user_id)
        row = await session.execute(query)
        return row.scalar_one_or_none()

    @staticmethod
    async def add_user(session: AsyncSession, user: User) -> UUID | None:
        """Add a new user to the database."""
        session.add(user)
        try:
            await session.commit()
            return user.id
        except IntegrityError as err:
            await session.rollback()
            raise exceptions.ItemAlreadyExistsError("User already exists") from err

    @staticmethod
    async def get_users(
        session: AsyncSession, filter_by: dict | None = None
    ) -> list[User]:
        """Retrieve a list of users based on optional filter criteria."""
        filters = filter_by or {}
        query = select(User).filter_by(**filters)
        rows = await session.execute(query)
        return list(rows.scalars())

    @staticmethod
    async def delete_user(session: AsyncSession, user: User) -> None:
        """Delete a user from the database."""
        await session.delete(user)
        try:
            await session.commit()
        except SQLAlchemyError as err:
            await session.rollback()
            raise exceptions.DatabaseError("Failed to delete payment") from err
