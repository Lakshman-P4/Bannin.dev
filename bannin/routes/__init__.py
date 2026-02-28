"""Bannin API sub-routers.

Shared helpers and router modules for the FastAPI application.
"""

from __future__ import annotations

import math
import time

from fastapi.responses import JSONResponse


def error_response(status_code: int, message: str, detail: str | None = None) -> JSONResponse:
    """Build a consistent JSON error response."""
    body: dict = {"error": message}
    if detail:
        body["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


def parse_since(since_str: str) -> float | None:
    """Parse human time strings like '1h', '30m', '7d' into epoch timestamp."""
    s = since_str.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            try:
                val = float(s[:-1])
                if val < 0 or not math.isfinite(val):
                    return None
                return time.time() - (val * mult)
            except ValueError:
                return None
    try:
        ts = float(s)
        # Only accept finite epoch timestamps from year 2020 onwards
        if not math.isfinite(ts) or ts < 1577836800:  # 2020-01-01T00:00:00Z
            return None
        return ts
    except ValueError:
        return None


def emit_event(event_type: str, source: str, severity: str, message: str, data: dict | None = None) -> None:
    """Emit an analytics event (non-blocking, best-effort)."""
    try:
        from bannin.analytics.pipeline import EventPipeline
        EventPipeline.get().emit({
            "type": event_type,
            "source": source,
            "severity": severity,
            "message": message,
            "data": data or {},
        })
    except Exception:
        from bannin.log import logger
        logger.debug("Failed to emit analytics event: %s", event_type, exc_info=True)
