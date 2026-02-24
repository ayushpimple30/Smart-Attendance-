from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        async with self._lock:
            timestamps = self._hits[client_ip]
            cutoff = now - self.window_seconds
            self._hits[client_ip] = [ts for ts in timestamps if ts > cutoff]

            if len(self._hits[client_ip]) >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too Many Requests"},
                )

            self._hits[client_ip].append(now)

        return await call_next(request)
