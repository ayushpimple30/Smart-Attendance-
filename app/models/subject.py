from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampedUUIDMixin

if TYPE_CHECKING:
    from app.models.session import Session
    from app.models.timetable import Timetable


class Subject(Base, TimestampedUUIDMixin):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("code", name="uq_subjects_code"),
        Index("ix_subjects_code", "code", unique=True),
        Index("ix_subjects_name", "name"),
        Index("ix_subjects_semester", "semester"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)

    timetable_entries: Mapped[list[Timetable]] = relationship(
        back_populates="subject",
        passive_deletes=True,
    )
    sessions: Mapped[list[Session]] = relationship(
        back_populates="subject",
        passive_deletes=True,
    )
