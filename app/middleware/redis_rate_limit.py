from __future__ import annotations

import os
import time

import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.metrics import RATE_LIMIT_HITS_TOTAL


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
        self.window_seconds = 60
        self.redis_client = redis.from_url(
            os.getenv("REDIS_URL", "redis://redis:6379/0"),
            decode_responses=True,
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        key = f"rate:{client_ip}:{int(time.time() // self.window_seconds)}"

        current = await self.redis_client.incr(key)
        if current == 1:
            await self.redis_client.expire(key, self.window_seconds)

        if current > self.rate_limit:
            RATE_LIMIT_HITS_TOTAL.inc()
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests"},
            )

        return await call_next(request)
