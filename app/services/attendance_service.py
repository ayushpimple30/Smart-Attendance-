from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.attendance import Attendance
from app.models.enums import AttendanceStatus, SessionStatus
from app.models.session import Session
from app.models.student import Student


class AttendanceError(Exception):
    pass


def compute_face_distance(known_encoding: list[float], incoming_encoding: list[float]) -> float:
    if not known_encoding or not incoming_encoding:
        raise AttendanceError("Face encoding cannot be empty.")
    if len(known_encoding) != len(incoming_encoding):
        raise AttendanceError("Face encoding length mismatch.")

    known = np.array(known_encoding, dtype=np.float64)
    incoming = np.array(incoming_encoding, dtype=np.float64)

    return float(np.linalg.norm(known - incoming))


async def validate_active_session(db: AsyncSession, session_id: UUID) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if session is None:
        raise AttendanceError("Session not found.")
    if session.status != SessionStatus.ACTIVE:
        raise AttendanceError("Attendance can only be marked for active sessions.")

    return session


async def _check_duplicate_attendance(db: AsyncSession, session_id: UUID, student_id: UUID) -> None:
    result = await db.execute(
        select(Attendance).where(
            Attendance.session_id == session_id,
            Attendance.student_id == student_id,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise AttendanceError("Attendance already marked for this student in this session.")


async def match_student_by_face(
    db: AsyncSession,
    encoding: list[float],
) -> tuple[Student, float]:
    if not encoding:
        raise AttendanceError("Incoming face encoding cannot be empty.")

    result = await db.execute(select(Student).where(Student.face_encoding.is_not(None)))
    students = list(result.scalars().all())

    if not students:
        raise AttendanceError("No student face encodings are registered.")

    threshold = float(getattr(settings, "face_match_threshold", 0.6))

    best_student: Student | None = None
    best_distance: float | None = None
    tie_count = 0

    for student in students:
        stored_encoding: Any = student.face_encoding
        if not isinstance(stored_encoding, list) or not stored_encoding:
            continue

        distance = compute_face_distance(stored_encoding, encoding)

        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_student = student
            tie_count = 1
        elif distance == best_distance:
            tie_count += 1

    if best_student is None or best_distance is None:
        raise AttendanceError("No valid student face encodings available for matching.")

    if tie_count > 1:
        raise AttendanceError("Ambiguous face match detected.")

    if best_distance > threshold:
        raise AttendanceError("Face did not match any registered student.")

    return best_student, best_distance


async def mark_attendance(
    db: AsyncSession,
    session_id: UUID,
    face_encoding: list[float],
) -> Attendance:
    if not face_encoding:
        raise AttendanceError("Incoming face encoding cannot be empty.")

    await validate_active_session(db=db, session_id=session_id)
    matched_student, distance = await match_student_by_face(db=db, encoding=face_encoding)
    await _check_duplicate_attendance(
        db=db,
        session_id=session_id,
        student_id=matched_student.id,
    )

    attendance = Attendance(
        session_id=session_id,
        student_id=matched_student.id,
        status=AttendanceStatus.PRESENT,
        confidence_score=max(0.0, min(1.0, 1.0 - float(distance))),
        marked_at=datetime.now(timezone.utc),
    )

    db.add(attendance)
    await db.commit()
    await db.refresh(attendance)

    return attendance
