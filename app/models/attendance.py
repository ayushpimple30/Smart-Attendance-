from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedUUIDMixin
from app.models.enums import AttendanceStatus

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.student import Student


class Attendance(Base, TimestampedUUIDMixin):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
        Index("ix_attendance_session_id", "session_id"),
        Index("ix_attendance_student_id", "student_id"),
        Index("ix_attendance_marked_at", "marked_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        SQLEnum(AttendanceStatus, name="attendance_status", create_constraint=True),
        nullable=False,
    )
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped[Session] = relationship(back_populates="attendance_records")
    student: Mapped[Student] = relationship(back_populates="attendance_records")
