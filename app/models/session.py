from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SQLEnum
from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedUUIDMixin
from app.models.enums import SessionStatus, SessionType

if TYPE_CHECKING:
    from app.models.attendance import Attendance
    from app.models.faculty import Faculty
    from app.models.subject import Subject


class Session(Base, TimestampedUUIDMixin):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_start_time", "start_time"),
        Index("ix_sessions_status", "status"),
        Index("ix_sessions_faculty_id", "faculty_id"),
        Index("ix_sessions_division_id", "division_id"),
        Index("ix_sessions_timetable_id", "timetable_id"),
        Index("ix_sessions_subject_id", "subject_id"),
    )

    timetable_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("timetables.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    faculty_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("faculties.id", ondelete="CASCADE"),
        nullable=False,
    )
    division_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("divisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_type: Mapped[SessionType] = mapped_column(
        SQLEnum(SessionType, name="session_type", create_constraint=True),
        nullable=False,
    )
    status: Mapped[SessionStatus] = mapped_column(
        SQLEnum(SessionStatus, name="session_status", create_constraint=True),
        nullable=False,
        default=SessionStatus.NOT_STARTED,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    subject: Mapped[Subject] = relationship(back_populates="sessions")
    faculty: Mapped[Faculty] = relationship(back_populates="sessions")
    attendance_records: Mapped[list[Attendance]] = relationship(
        back_populates="session",
        passive_deletes=True,
    )
