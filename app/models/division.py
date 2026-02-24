from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedUUIDMixin

if TYPE_CHECKING:
    from app.models.batch import Batch
    from app.models.student import Student
    from app.models.timetable import Timetable


class Division(Base, TimestampedUUIDMixin):
    __tablename__ = "divisions"
    __table_args__ = (
        UniqueConstraint("name", name="uq_divisions_name"),
        Index("ix_divisions_name", "name", unique=True),
        Index("ix_divisions_year", "year"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    students: Mapped[list[Student]] = relationship(
        back_populates="division",
        passive_deletes=True,
    )
    batches: Mapped[list[Batch]] = relationship(
        back_populates="division",
        passive_deletes=True,
    )
    timetable_entries: Mapped[list[Timetable]] = relationship(
        back_populates="division",
        passive_deletes=True,
    )
