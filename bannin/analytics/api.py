"""Analytics dashboard REST API -- serves historical data and the analytics UI.

Runs on port 8421, separate from the main agent (8420). Both can access
the same SQLite store.db simultaneously via WAL mode.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from bannin.log import logger
from bannin.routes import parse_since

try:
    _DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
except FileNotFoundError:
    _DASHBOARD_HTML = "<h1>Bannin Analytics</h1><p>Dashboard file not found.</p>"

from starlette.requests import Request as StarletteRequest

app = FastAPI(
    title="Bannin Analytics",
    description="Historical event analytics and trend dashboard",
    version="0.1.0",
)


@app.exception_handler(Exception)
async def _global_exception_handler(request: StarletteRequest, exc: Exception) -> JSONResponse:
    logger.warning("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8420",
        "http://127.0.0.1:8420",
        "http://localhost:8421",
        "http://127.0.0.1:8421",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    return HTMLResponse(content=_DASHBOARD_HTML)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "analytics"}


@app.get("/stats")
def stats() -> dict:
    from bannin.analytics.store import AnalyticsStore
    return AnalyticsStore.get().get_stats()


@app.get("/events")
def events(
    event_type: str = Query(default="", max_length=128),
    severity: str = Query(default="", max_length=32),
    since: str = Query(default="", max_length=64),
    limit: int = Query(default=200, ge=1, le=5000),
) -> dict:
    from bannin.analytics.store import AnalyticsStore
    since_ts = parse_since(since) if since else None
    return {
        "events": AnalyticsStore.get().query(
            event_type=event_type or None,
            severity=severity or None,
            since=since_ts,
            limit=limit,
        )
    }


@app.get("/search", response_model=None)
def search(q: str = Query(default="", max_length=500), limit: int = Query(default=50, ge=1, le=500)) -> dict | JSONResponse:
    from bannin.analytics.store import AnalyticsStore
    if not q:
        return JSONResponse(status_code=400, content={"error": "Missing required parameter: q", "detail": "Provide ?q=search+term"})
    return {"results": AnalyticsStore.get().search(q, limit=limit)}


@app.get("/timeline")
def timeline(
    since: str = Query(default="1h", max_length=64),
    limit: int = Query(default=200, ge=1, le=5000),
    types: str = Query(default="", max_length=500),
) -> dict:
    from bannin.analytics.store import AnalyticsStore
    since_ts = parse_since(since) if since else None
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    return {"timeline": AnalyticsStore.get().get_timeline(since=since_ts, limit=limit, types=type_list)}


@app.get("/cost")
def cost_trend(days: int = Query(default=7, ge=1, le=365)) -> dict:
    from bannin.analytics.store import AnalyticsStore
    return {"cost_trend": AnalyticsStore.get().get_cost_trend(days=days)}
