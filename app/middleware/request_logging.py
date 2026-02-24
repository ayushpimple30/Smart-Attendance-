from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.metrics import ACTIVE_REQUESTS, HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL

logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        ACTIVE_REQUESTS.inc()
        try:
            response = await call_next(request)
        finally:
            ACTIVE_REQUESTS.dec()

        duration_s = time.perf_counter() - start
        duration_ms = round(duration_s * 1000, 2)

        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=request.url.path,
            status=str(response.status_code),
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            path=request.url.path,
        ).observe(duration_s)

        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else None,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

        return response
