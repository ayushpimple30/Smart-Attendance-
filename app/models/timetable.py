from __future__ import annotations

import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Index, Integer, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedUUIDMixin
from app.models.enums import SessionType

if TYPE_CHECKING:
    from app.models.batch import Batch
    from app.models.division import Division
    from app.models.faculty import Faculty
    from app.models.subject import Subject


class Timetable(Base, TimestampedUUIDMixin):
    __tablename__ = "timetables"
    __table_args__ = (
        UniqueConstraint(
            "day_of_week",
            "start_time",
            "division_id",
            "batch_id",
            name="uq_timetables_slot_division_batch",
        ),
        Index("ix_timetables_day_of_week", "day_of_week"),
        Index("ix_timetables_start_time", "start_time"),
        Index("ix_timetables_faculty_id", "faculty_id"),
        Index("ix_timetables_division_id", "division_id"),
        Index("ix_timetables_batch_id", "batch_id"),
        Index("ix_timetables_subject_id", "subject_id"),
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
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    end_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    session_type: Mapped[SessionType] = mapped_column(
        SQLEnum(SessionType, name="session_type", create_constraint=True),
        nullable=False,
    )

    subject: Mapped[Subject] = relationship(back_populates="timetable_entries")
    faculty: Mapped[Faculty] = relationship(back_populates="timetable_entries")
    division: Mapped[Division] = relationship(back_populates="timetable_entries")
    batch: Mapped[Batch | None] = relationship(back_populates="timetable_entries")
