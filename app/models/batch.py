from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedUUIDMixin

if TYPE_CHECKING:
    from app.models.division import Division
    from app.models.student import Student
    from app.models.timetable import Timetable


class Batch(Base, TimestampedUUIDMixin):
    __tablename__ = "batches"
    __table_args__ = (
        UniqueConstraint("name", "division_id", name="uq_batches_name_division_id"),
        Index("ix_batches_division_id", "division_id"),
        Index("ix_batches_name", "name"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    division_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("divisions.id", ondelete="CASCADE"),
        nullable=False,
    )

    division: Mapped[Division] = relationship(back_populates="batches")
    students: Mapped[list[Student]] = relationship(
        back_populates="batch",
        passive_deletes=True,
    )
    timetable_entries: Mapped[list[Timetable]] = relationship(
        back_populates="batch",
        passive_deletes=True,
    )
