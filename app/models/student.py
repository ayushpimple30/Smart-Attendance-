from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedUUIDMixin

if TYPE_CHECKING:
    from app.models.attendance import Attendance
    from app.models.batch import Batch
    from app.models.division import Division
    from app.models.user import User


class Student(Base, TimestampedUUIDMixin):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_students_user_id"),
        UniqueConstraint("division_id", "roll_number", name="uq_students_division_roll_number"),
        Index("ix_students_user_id", "user_id"),
        Index("ix_students_roll_number", "roll_number"),
        Index("ix_students_division_id", "division_id"),
        Index("ix_students_batch_id", "batch_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    roll_number: Mapped[str] = mapped_column(String(50), nullable=False)
    division_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("divisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("batches.id", ondelete="SET NULL"),
        nullable=True,
    )
    face_encoding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    user: Mapped[User] = relationship(back_populates="student")
    division: Mapped[Division] = relationship(back_populates="students")
    batch: Mapped[Batch | None] = relationship(back_populates="students")
    attendance_records: Mapped[list[Attendance]] = relationship(
        back_populates="student",
        passive_deletes=True,
    )
