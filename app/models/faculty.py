from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedUUIDMixin

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.timetable import Timetable
    from app.models.user import User


class Faculty(Base, TimestampedUUIDMixin):
    __tablename__ = "faculties"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_faculties_user_id"),
        Index("ix_faculties_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)

    user: Mapped[User] = relationship(back_populates="faculty")
    sessions: Mapped[list[Session]] = relationship(
        back_populates="faculty",
        passive_deletes=True,
    )
    timetable_entries: Mapped[list[Timetable]] = relationship(
        back_populates="faculty",
        passive_deletes=True,
    )
