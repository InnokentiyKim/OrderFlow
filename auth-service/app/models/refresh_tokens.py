import uuid
from datetime import datetime, UTC, timedelta

from sqlalchemy import TIMESTAMP, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import MappedAsDataclass, Mapped, mapped_column

from app.common.model import Base


class AuthenticationBase(MappedAsDataclass, Base):
    """Base class for SQLAlchemy connector ORM models."""

    __abstract__ = True


class RefreshToken(AuthenticationBase):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    issued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __init__(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        token_lifetime_minutes: int,
    ):
        self.id = uuid.uuid4()
        self.user_id = user_id
        self.token_hash = token_hash

        now = datetime.now(UTC)
        self.issued_at = now
        self.expires_at = now + timedelta(minutes=token_lifetime_minutes)
        self.revoked = False
        self.revoked_at = None

        super().__init__()

    def is_expired(self) -> bool:
        """Check if the refresh token has expired."""
        return datetime.now(UTC) >= self.expires_at

    @property
    def is_revoked(self) -> bool:
        """Check if the refresh token has been revoked."""
        return self.revoked

    def revoke(self) -> None:
        """Revoke the refresh token."""
        self.revoked = True
        self.revoked_at = datetime.now(UTC)
