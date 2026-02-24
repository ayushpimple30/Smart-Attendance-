from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.database import AsyncSessionLocal
from app.services.session_service import generate_sessions_for_date, process_session_transitions

logger = logging.getLogger(__name__)


class SessionScheduler:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone=timezone.utc)

    def start(self) -> None:
        self._scheduler.add_job(
            self._run_daily_generation,
            trigger=CronTrigger(hour=0, minute=5, timezone=timezone.utc),
            id="daily_session_generation",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        self._scheduler.add_job(
            self._run_session_transitions,
            trigger=IntervalTrigger(minutes=1, timezone=timezone.utc),
            id="session_transition_processor",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Session scheduler started")

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Session scheduler shut down")

    async def _run_daily_generation(self) -> None:
        target_date = datetime.now(timezone.utc).date()
        try:
            async with AsyncSessionLocal() as db:
                created = await generate_sessions_for_date(db, target_date)
                logger.info(
                    "Daily session generation completed",
                    extra={"target_date": target_date.isoformat(), "created_count": len(created)},
                )
        except Exception:
            logger.exception("Daily session generation failed")

    async def _run_session_transitions(self) -> None:
        try:
            async with AsyncSessionLocal() as db:
                activated_count, completed_count = await process_session_transitions(db)
                if activated_count or completed_count:
                    logger.info(
                        "Session transitions processed",
                        extra={
                            "activated_count": activated_count,
                            "completed_count": completed_count,
                        },
                    )
        except Exception:
            logger.exception("Session transition processing failed")


async def _serve_scheduler() -> None:
    scheduler = SessionScheduler()
    scheduler.start()
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(_serve_scheduler())
