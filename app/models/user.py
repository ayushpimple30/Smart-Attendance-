from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum as SQLEnum, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedUUIDMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.faculty import Faculty
    from app.models.student import Student


class User(Base, TimestampedUUIDMixin):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_email", "email"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    student: Mapped[Student | None] = relationship(
        back_populates="user",
        uselist=False,
        passive_deletes=True,
    )
    faculty: Mapped[Faculty | None] = relationship(
        back_populates="user",
        uselist=False,
        passive_deletes=True,
    )
