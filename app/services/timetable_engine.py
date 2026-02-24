from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SessionType
from app.models.timetable import Timetable

COLLEGE_START_TIME = time(9, 0)
COLLEGE_END_TIME = time(16, 0)

TEA_BREAK_START = time(11, 0)
TEA_BREAK_END = time(11, 15)
LUNCH_BREAK_START = time(13, 15)
LUNCH_BREAK_END = time(14, 15)

LECTURE_DURATION_MINUTES = 60
PRACTICAL_DURATION_MINUTES = 120


class TimetableValidationError(Exception):
    pass


def _normalize_session_type(value: SessionType | str) -> SessionType:
    if isinstance(value, SessionType):
        return value

    try:
        return SessionType(str(value))
    except ValueError as exc:
        raise TimetableValidationError("Invalid session type.") from exc


def _duration_minutes(start_time: time, end_time: time) -> int:
    reference_date = date(2000, 1, 1)
    start_dt = datetime.combine(reference_date, start_time)
    end_dt = datetime.combine(reference_date, end_time)
    return int((end_dt - start_dt).total_seconds() // 60)


def _is_overlap(start_1: time, end_1: time, start_2: time, end_2: time) -> bool:
    return start_1 < end_2 and start_2 < end_1


def _validate_duration(session_type: SessionType, start_time: time, end_time: time) -> None:
    duration_minutes = _duration_minutes(start_time=start_time, end_time=end_time)
    expected_minutes = (
        LECTURE_DURATION_MINUTES
        if session_type == SessionType.LECTURE
        else PRACTICAL_DURATION_MINUTES
    )

    if duration_minutes != expected_minutes:
        raise TimetableValidationError(
            f"Invalid duration for {session_type.value}."
        )


def _validate_college_hours(start_time: time, end_time: time) -> None:
    if start_time >= end_time:
        raise TimetableValidationError("Start time must be earlier than end time.")
    if start_time < COLLEGE_START_TIME or end_time > COLLEGE_END_TIME:
        raise TimetableValidationError("Session must be within college hours (09:00-16:00).")


def _validate_break_overlap(start_time: time, end_time: time) -> None:
    if _is_overlap(start_time, end_time, TEA_BREAK_START, TEA_BREAK_END):
        raise TimetableValidationError("Session overlaps tea break (11:00-11:15).")
    if _is_overlap(start_time, end_time, LUNCH_BREAK_START, LUNCH_BREAK_END):
        raise TimetableValidationError("Session overlaps lunch break (13:15-14:15).")


async def _validate_conflicts(db: AsyncSession, timetable_entry: Timetable) -> None:
    overlap_clause = and_(
        Timetable.start_time < timetable_entry.end_time,
        timetable_entry.start_time < Timetable.end_time,
    )

    base_query = select(Timetable).where(
        Timetable.day_of_week == timetable_entry.day_of_week,
        overlap_clause,
    )

    faculty_query = base_query.where(Timetable.faculty_id == timetable_entry.faculty_id)
    faculty_result = await db.execute(faculty_query)
    if faculty_result.scalar_one_or_none() is not None:
        raise TimetableValidationError("Faculty has a conflicting timetable slot.")

    if timetable_entry.batch_id is None:
        division_conflict_query = base_query.where(
            Timetable.division_id == timetable_entry.division_id
        )
    else:
        division_conflict_query = base_query.where(
            Timetable.division_id == timetable_entry.division_id,
            or_(
                Timetable.batch_id == timetable_entry.batch_id,
                Timetable.batch_id.is_(None),
            ),
        )

    division_result = await db.execute(division_conflict_query)
    if division_result.scalar_one_or_none() is not None:
        raise TimetableValidationError("Division or batch has a conflicting timetable slot.")


def _validate_day_of_week(day_of_week: int) -> None:
    if day_of_week < 0 or day_of_week > 6:
        raise TimetableValidationError("day_of_week must be between 0 and 6.")


async def create_timetable_entry(db: AsyncSession, data: dict[str, Any]) -> Timetable:
    required_fields = {
        "subject_id",
        "faculty_id",
        "division_id",
        "day_of_week",
        "start_time",
        "end_time",
        "session_type",
    }

    missing_fields = sorted(required_fields - data.keys())
    if missing_fields:
        raise TimetableValidationError(
            f"Missing required fields: {', '.join(missing_fields)}"
        )

    session_type = _normalize_session_type(data["session_type"])
    start_time = data["start_time"]
    end_time = data["end_time"]

    if not isinstance(start_time, time) or not isinstance(end_time, time):
        raise TimetableValidationError("start_time and end_time must be time values.")

    _validate_day_of_week(int(data["day_of_week"]))
    _validate_college_hours(start_time=start_time, end_time=end_time)
    _validate_break_overlap(start_time=start_time, end_time=end_time)
    _validate_duration(session_type=session_type, start_time=start_time, end_time=end_time)

    timetable_entry = Timetable(
        subject_id=data["subject_id"],
        faculty_id=data["faculty_id"],
        division_id=data["division_id"],
        batch_id=data.get("batch_id"),
        day_of_week=int(data["day_of_week"]),
        start_time=start_time,
        end_time=end_time,
        session_type=session_type,
    )

    await _validate_conflicts(db=db, timetable_entry=timetable_entry)

    db.add(timetable_entry)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise TimetableValidationError("Failed to create timetable entry.") from exc

    await db.refresh(timetable_entry)
    return timetable_entry
