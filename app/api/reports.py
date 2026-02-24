from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import get_current_user
from app.models.attendance import Attendance
from app.models.batch import Batch
from app.models.division import Division
from app.models.enums import AttendanceStatus, SessionStatus, UserRole
from app.models.faculty import Faculty
from app.models.session import Session
from app.models.student import Student
from app.models.user import User

router = APIRouter(prefix="/reports", tags=["Reports"])


class SessionStudentAttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: UUID
    roll_number: str
    status: AttendanceStatus
    confidence_score: float | None
    marked_at: datetime | None


class SessionAttendanceReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    records: list[SessionStudentAttendanceResponse]


class StudentSessionReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: UUID
    status: AttendanceStatus
    confidence_score: float | None
    marked_at: datetime | None


class StudentAttendanceReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: UUID
    total_sessions: int
    present_sessions: int
    attendance_percentage: float
    sessions: list[StudentSessionReportItem]


class DivisionStudentSummaryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: UUID
    roll_number: str
    total_sessions: int
    present_sessions: int
    attendance_percentage: float


class DivisionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    division_id: UUID
    students: list[DivisionStudentSummaryItem]


async def _get_session_or_404(db: AsyncSession, session_id: UUID) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session_obj = result.scalar_one_or_none()
    if session_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return session_obj


async def _get_student_or_404(db: AsyncSession, student_id: UUID) -> Student:
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    return student


async def _get_division_or_404(db: AsyncSession, division_id: UUID) -> Division:
    result = await db.execute(select(Division).where(Division.id == division_id))
    division = result.scalar_one_or_none()
    if division is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Division not found.")
    return division


async def _get_faculty_by_user(db: AsyncSession, user_id: UUID) -> Faculty | None:
    result = await db.execute(select(Faculty).where(Faculty.user_id == user_id))
    return result.scalar_one_or_none()


def _pct(present: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((present / total) * 100.0, 2)


@router.get("/session/{session_id}", response_model=SessionAttendanceReportResponse)
async def get_session_report(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> SessionAttendanceReportResponse:
    session_obj = await _get_session_or_404(db, session_id)

    if current_user.role == UserRole.FACULTY:
        faculty = await _get_faculty_by_user(db, current_user.id)
        if faculty is None or faculty.id != session_obj.faculty_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    student_filter = [Student.division_id == session_obj.division_id]
    if session_obj.batch_id is not None:
        student_filter.append(Student.batch_id == session_obj.batch_id)

    result = await db.execute(
        select(
            Student.id,
            Student.roll_number,
            Attendance.status,
            Attendance.confidence_score,
            Attendance.marked_at,
        )
        .outerjoin(
            Attendance,
            and_(
                Attendance.student_id == Student.id,
                Attendance.session_id == session_id,
            ),
        )
        .where(*student_filter)
        .order_by(Student.roll_number.asc())
    )

    rows = result.all()
    records = [
        SessionStudentAttendanceResponse(
            student_id=row.id,
            roll_number=row.roll_number,
            status=row.status if row.status is not None else AttendanceStatus.ABSENT,
            confidence_score=row.confidence_score,
            marked_at=row.marked_at,
        )
        for row in rows
    ]

    return SessionAttendanceReportResponse(session_id=session_id, records=records)


@router.get("/student/{student_id}", response_model=StudentAttendanceReportResponse)
async def get_student_report(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> StudentAttendanceReportResponse:
    student = await _get_student_or_404(db, student_id)

    if current_user.role == UserRole.STUDENT:
        if current_user.id != student.user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    elif current_user.role == UserRole.FACULTY:
        faculty = await _get_faculty_by_user(db, current_user.id)
        if faculty is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        session_access_query = select(func.count(Session.id)).where(
            Session.faculty_id == faculty.id,
            Session.division_id == student.division_id,
            Session.status == SessionStatus.COMPLETED,
            Session.start_time <= datetime.now(timezone.utc),
        )
        if student.batch_id is not None:
            session_access_query = session_access_query.where(
                or_(Session.batch_id.is_(None), Session.batch_id == student.batch_id)
            )

        access_count = await db.scalar(session_access_query)
        if not access_count:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    now_utc = datetime.now(timezone.utc)

    session_scope_filters = [
        Session.division_id == student.division_id,
        Session.status == SessionStatus.COMPLETED,
        Session.start_time <= now_utc,
    ]
    if student.batch_id is not None:
        session_scope_filters.append(
            or_(Session.batch_id.is_(None), Session.batch_id == student.batch_id)
        )

    sessions_result = await db.execute(
        select(
            Session.id,
            Attendance.status,
            Attendance.confidence_score,
            Attendance.marked_at,
        )
        .outerjoin(
            Attendance,
            and_(
                Attendance.session_id == Session.id,
                Attendance.student_id == student_id,
            ),
        )
        .where(*session_scope_filters)
        .order_by(Session.start_time.asc())
    )

    session_rows = sessions_result.all()

    sessions = [
        StudentSessionReportItem(
            session_id=row.id,
            status=row.status if row.status is not None else AttendanceStatus.ABSENT,
            confidence_score=row.confidence_score,
            marked_at=row.marked_at,
        )
        for row in session_rows
    ]

    total_sessions = len(session_rows)
    present_sessions = sum(1 for item in sessions if item.status == AttendanceStatus.PRESENT)

    return StudentAttendanceReportResponse(
        student_id=student_id,
        total_sessions=total_sessions,
        present_sessions=present_sessions,
        attendance_percentage=_pct(present_sessions, total_sessions),
        sessions=sessions,
    )


@router.get("/division/{division_id}/summary", response_model=DivisionSummaryResponse)
async def get_division_summary(
    division_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> DivisionSummaryResponse:
    await _get_division_or_404(db, division_id)

    if current_user.role == UserRole.FACULTY:
        faculty = await _get_faculty_by_user(db, current_user.id)
        if faculty is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        teach_count = await db.scalar(
            select(func.count(Session.id)).where(
                Session.faculty_id == faculty.id,
                Session.division_id == division_id,
            )
        )
        if not teach_count:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    now_utc = datetime.now(timezone.utc)

    total_sessions_subq = (
        select(
            Student.id.label("student_id"),
            func.count(Session.id).label("total_sessions"),
        )
        .join(
            Session,
            and_(
                Session.division_id == Student.division_id,
                or_(Session.batch_id.is_(None), Session.batch_id == Student.batch_id),
                Session.status == SessionStatus.COMPLETED,
                Session.start_time <= now_utc,
            ),
        )
        .where(Student.division_id == division_id)
        .group_by(Student.id)
        .subquery()
    )

    present_sessions_subq = (
        select(
            Attendance.student_id.label("student_id"),
            func.count(Attendance.id).label("present_sessions"),
        )
        .join(Session, Session.id == Attendance.session_id)
        .join(Student, Student.id == Attendance.student_id)
        .where(
            Student.division_id == division_id,
            Attendance.status == AttendanceStatus.PRESENT,
            Session.status == SessionStatus.COMPLETED,
            Session.start_time <= now_utc,
        )
        .group_by(Attendance.student_id)
        .subquery()
    )

    result = await db.execute(
        select(
            Student.id,
            Student.roll_number,
            func.coalesce(total_sessions_subq.c.total_sessions, 0).label("total_sessions"),
            func.coalesce(present_sessions_subq.c.present_sessions, 0).label("present_sessions"),
        )
        .outerjoin(total_sessions_subq, total_sessions_subq.c.student_id == Student.id)
        .outerjoin(present_sessions_subq, present_sessions_subq.c.student_id == Student.id)
        .where(Student.division_id == division_id)
        .order_by(Student.roll_number.asc())
    )

    students = []
    for row in result.all():
        total_sessions = int(row.total_sessions)
        present_sessions = int(row.present_sessions)
        students.append(
            DivisionStudentSummaryItem(
                student_id=row.id,
                roll_number=row.roll_number,
                total_sessions=total_sessions,
                present_sessions=present_sessions,
                attendance_percentage=_pct(present_sessions, total_sessions),
            )
        )

    return DivisionSummaryResponse(division_id=division_id, students=students)
