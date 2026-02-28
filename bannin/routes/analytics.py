"""Analytics endpoints -- stats, events, search, timeline."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from bannin.routes import error_response, parse_since

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/stats")
def analytics_stats() -> dict:
    """Analytics store statistics -- event counts, DB size, time range."""
    from bannin.analytics.store import AnalyticsStore
    return AnalyticsStore.get().get_stats()


@router.get("/events")
def analytics_events(
    event_type: str = Query(default="", max_length=256),
    severity: str = Query(default="", max_length=256),
    since: str = Query(default="", max_length=64),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    """Query stored analytics events with optional filters."""
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


@router.get("/search", response_model=None)
def analytics_search(q: str = Query(default="", max_length=500), limit: int = Query(default=50, ge=1, le=500)) -> dict | JSONResponse:
    """Full-text search across stored events."""
    from bannin.analytics.store import AnalyticsStore
    if not q:
        return error_response(400, "Missing required parameter: q", "Provide ?q=search+term")
    return {"results": AnalyticsStore.get().search(q, limit=limit)}


@router.get("/timeline")
def analytics_timeline(since: str = Query(default="", max_length=64), limit: int = Query(default=200, ge=1, le=1000), types: str = Query(default="", max_length=2000)) -> dict:
    """Event timeline, newest first. Optionally filter by comma-separated event types."""
    from bannin.analytics.store import AnalyticsStore
    since_ts = parse_since(since) if since else None
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    return {"timeline": AnalyticsStore.get().get_timeline(since=since_ts, limit=limit, types=type_list)}
