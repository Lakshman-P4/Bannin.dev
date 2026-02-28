"""LLM endpoints -- usage, calls, context, latency, health, connections."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from bannin.routes import error_response

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/usage")
def llm_usage() -> dict:
    """LLM token and cost tracking summary."""
    from bannin.llm.tracker import LLMTracker
    return LLMTracker.get().get_summary()


@router.get("/calls")
def llm_calls(limit: int = Query(default=20, ge=1, le=500)) -> dict:
    """Recent LLM API calls."""
    from bannin.llm.tracker import LLMTracker
    return {"calls": LLMTracker.get().get_calls(limit=limit)}


@router.get("/context", response_model=None)
def llm_context(model: str = Query(default="", max_length=256), tokens: int = Query(default=0, ge=0, le=10_000_000)) -> dict | JSONResponse:
    """Context window usage prediction for a model."""
    from bannin.llm.tracker import LLMTracker
    if not model:
        return error_response(400, "Missing required parameter: model", "Provide ?model=gpt-4o&tokens=50000")
    return LLMTracker.get().get_context_usage(model, tokens)


@router.get("/latency")
def llm_latency(model: str = Query(default="", max_length=256)) -> dict:
    """Latency trend analysis."""
    from bannin.llm.tracker import LLMTracker
    return LLMTracker.get().get_latency_trend(model=model or None)


@router.get("/health")
def llm_health(source: str = Query(default="", max_length=256)) -> dict:
    """Unified conversation health score across all signal sources."""
    from bannin.llm.aggregator import compute_health
    return compute_health(source_filter=source)


@router.get("/connections")
def llm_connections() -> dict:
    """Auto-detected LLM tools and connections on this system."""
    from bannin.llm.connections import LLMConnectionScanner
    return {"connections": LLMConnectionScanner.get().get_connections()}
