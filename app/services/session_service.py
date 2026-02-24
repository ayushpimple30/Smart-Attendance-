from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import SessionStatus
from app.models.session import Session
from app.models.timetable import Timetable


async def generate_sessions_for_date(db: AsyncSession, target_date: date) -> list[Session]:
    day_start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
    weekday = target_date.weekday()

    timetable_result = await db.execute(
        select(Timetable).where(Timetable.day_of_week == weekday)
    )
    timetable_entries = list(timetable_result.scalars().all())

    if not timetable_entries:
        return []

    timetable_ids = [entry.id for entry in timetable_entries]
    existing_result = await db.execute(
        select(Session.timetable_id).where(
            Session.timetable_id.in_(timetable_ids),
            and_(Session.start_time >= day_start, Session.start_time <= day_end),
        )
    )
    existing_timetable_ids = set(existing_result.scalars().all())

    new_sessions: list[Session] = []
    for entry in timetable_entries:
        if entry.id in existing_timetable_ids:
            continue

        session_start = datetime.combine(target_date, entry.start_time, tzinfo=timezone.utc)
        session_end = datetime.combine(target_date, entry.end_time, tzinfo=timezone.utc)

        new_sessions.append(
            Session(
                timetable_id=entry.id,
                subject_id=entry.subject_id,
                faculty_id=entry.faculty_id,
                division_id=entry.division_id,
                batch_id=entry.batch_id,
                session_type=entry.session_type,
                status=SessionStatus.NOT_STARTED,
                start_time=session_start,
                end_time=session_end,
            )
        )

    if not new_sessions:
        return []

    db.add_all(new_sessions)
    await db.commit()
    for session in new_sessions:
        await db.refresh(session)

    return new_sessions


async def process_session_transitions(db: AsyncSession) -> tuple[int, int]:
    now_utc = datetime.now(timezone.utc)

    not_started_result = await db.execute(
        select(Session).where(
            Session.status == SessionStatus.NOT_STARTED,
            Session.start_time <= now_utc,
        )
    )
    not_started_sessions = list(not_started_result.scalars().all())

    active_result = await db.execute(
        select(Session).where(
            Session.status == SessionStatus.ACTIVE,
            Session.end_time <= now_utc,
        )
    )
    active_sessions = list(active_result.scalars().all())

    for session in not_started_sessions:
        session.status = SessionStatus.ACTIVE
        session.actual_start_time = now_utc

    for session in active_sessions:
        session.status = SessionStatus.COMPLETED
        session.actual_end_time = now_utc

    if not_started_sessions or active_sessions:
        await db.commit()

    return len(not_started_sessions), len(active_sessions)
