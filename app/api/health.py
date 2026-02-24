from __future__ import annotations

import os

import redis.asyncio as redis
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.database import engine

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/ready")
async def readiness() -> JSONResponse:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    try:
        client = redis.from_url(redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    return JSONResponse(status_code=200, content={"status": "ready"})
