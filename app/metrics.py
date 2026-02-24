from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter(tags=["Metrics"])

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
ACTIVE_REQUESTS = Gauge(
    "active_requests",
    "Number of active HTTP requests",
)
RATE_LIMIT_HITS_TOTAL = Counter(
    "rate_limit_hits_total",
    "Total rate limit hits",
)
DB_QUERY_FAILURES_TOTAL = Counter(
    "db_query_failures_total",
    "Total DB query failures",
)


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
