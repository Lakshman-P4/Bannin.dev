"""Analytics dashboard REST API -- serves historical data and the analytics UI.

Runs on port 8421, separate from the main agent (8420). Both can access
the same SQLite store.db simultaneously via WAL mode.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

try:
    _DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
except FileNotFoundError:
    _DASHBOARD_HTML = "<h1>Bannin Analytics</h1><p>Dashboard file not found.</p>"

app = FastAPI(
    title="Bannin Analytics",
    description="Historical event analytics and trend dashboard",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return HTMLResponse(content=_DASHBOARD_HTML)


@app.get("/health")
def health():
    return {"status": "ok", "service": "analytics"}


@app.get("/stats")
def stats():
    from bannin.analytics.store import AnalyticsStore
    return AnalyticsStore.get().get_stats()


@app.get("/events")
def events(type: str = "", severity: str = "", since: str = "", limit: int = 200):
    from bannin.analytics.store import AnalyticsStore
    since_ts = _parse_since(since) if since else None
    return {
        "events": AnalyticsStore.get().query(
            event_type=type or None,
            severity=severity or None,
            since=since_ts,
            limit=limit,
        )
    }


@app.get("/search")
def search(q: str = "", limit: int = 50):
    from bannin.analytics.store import AnalyticsStore
    if not q:
        return {"error": "Provide ?q=search+term"}
    return {"results": AnalyticsStore.get().search(q, limit=limit)}


@app.get("/timeline")
def timeline(since: str = "1h", limit: int = 200, types: str = ""):
    from bannin.analytics.store import AnalyticsStore
    since_ts = _parse_since(since) if since else None
    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
    return {"timeline": AnalyticsStore.get().get_timeline(since=since_ts, limit=limit, types=type_list)}


@app.get("/cost")
def cost_trend(days: int = 7):
    from bannin.analytics.store import AnalyticsStore
    return {"cost_trend": AnalyticsStore.get().get_cost_trend(days=days)}


def _parse_since(since_str: str) -> float | None:
    import time
    s = since_str.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            try:
                return time.time() - (float(s[:-1]) * mult)
            except ValueError:
                return None
    return None
