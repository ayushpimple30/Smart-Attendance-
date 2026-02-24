from __future__ import annotations

import logging
import os
import sys

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sqlalchemy import text

from app.api.health import router as health_router
from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.metrics import DB_QUERY_FAILURES_TOTAL, router as metrics_router
from app.middleware.redis_rate_limit import RedisRateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.services.session_scheduler import SessionScheduler

configure_logging()
logger = logging.getLogger("app.main")

APP_ENV = os.getenv("APP_ENV", settings.app_env)
RUN_SCHEDULER = os.getenv("RUN_SCHEDULER", "false").lower() == "true"

sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=0.2,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )


def _parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


async def _shutdown_scheduler(scheduler: SessionScheduler) -> None:
    await run_in_threadpool(scheduler.shutdown)


def _validate_startup_configuration() -> None:
    database_url = os.getenv("DATABASE_URL")
    secret_key = os.getenv("SECRET_KEY")

    if not database_url:
        logger.critical("missing_required_configuration", extra={"message": "DATABASE_URL is required"})
        sys.exit(1)

    if not secret_key:
        logger.critical("missing_required_configuration", extra={"message": "SECRET_KEY is required"})
        sys.exit(1)


app = FastAPI(
    title=settings.app_name,
    max_request_size=5 * 1024 * 1024,
    docs_url=None if APP_ENV == "production" else "/docs",
    redoc_url=None if APP_ENV == "production" else "/redoc",
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_exception",
        exc_info=exc,
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


@app.on_event("startup")
async def on_startup() -> None:
    _validate_startup_configuration()
    logger.info("application_starting", extra={"message": "Starting application", "app_env": APP_ENV})

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        DB_QUERY_FAILURES_TOTAL.inc()
        logger.critical("startup_database_check_failed", exc_info=exc)
        sys.exit(1)

    app.state.scheduler = None
    if RUN_SCHEDULER:
        app.state.scheduler = SessionScheduler()
        app.state.scheduler.start()

    logger.info(
        "application_started",
        extra={"message": "Application started", "app_env": APP_ENV, "scheduler_enabled": RUN_SCHEDULER},
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("application_shutdown_started", extra={"message": "Shutdown initiated"})
    scheduler: SessionScheduler | None = app.state.scheduler
    if scheduler is not None:
        await _shutdown_scheduler(scheduler)
    await engine.dispose()
    logger.info("application_shutdown_completed", extra={"message": "Shutdown completed"})


app.add_middleware(RequestIDMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RedisRateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(api_router, prefix=settings.api_v1_prefix)
