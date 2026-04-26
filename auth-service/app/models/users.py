import uuid
from datetime import datetime, UTC

from sqlalchemy import TIMESTAMP, String, Boolean, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import MappedAsDataclass, Mapped, mapped_column

from app.common.model import Base
from app.common.enums import UserRoleEnum


class UserBase(MappedAsDataclass, Base):
    """Base class for SQLAlchemy connector ORM models."""

    __abstract__ = True


class User(UserBase):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, primary_key=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRoleEnum] = mapped_column(SAEnum(UserRoleEnum), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __init__(
        self,
        email: str,
        hashed_password: str,
        role: UserRoleEnum,
        is_active: bool = True,
    ):
        self.id = uuid.uuid4()
        self.email = email
        self.hashed_password = hashed_password
        self.role = role
        self.is_active = is_active

        now = datetime.now(UTC)
        self.created_at = now
        self.updated_at = now

        super().__init__()

    def is_user(self) -> bool:
        """Check if the user has a regular user role."""
        return self.role == UserRoleEnum.USER

    def is_admin(self) -> bool:
        """Check if the user has an admin role."""
        return self.role == UserRoleEnum.ADMIN

    def is_active_user(self) -> bool:
        """Check if the user account is active."""
        return self.is_active

    def activate(self) -> None:
        """Activate the user account."""
        self.is_active = True
        self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        """Deactivate the user account."""
        self.is_active = False
        self.updated_at = datetime.now(UTC)
