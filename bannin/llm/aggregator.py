"""Health aggregator -- computes per-source and combined LLM health scores.

Orchestrates health computation across all signal sources (MCP sessions,
JSONL transcripts, Ollama, API tracker) and returns a unified result
with per-source breakdown and worst-of combined score.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bannin.log import logger
from bannin.state import get_mcp_sessions, get_mcp_session_data

if TYPE_CHECKING:
    from bannin.llm.tracker import LLMTracker


def compute_health(source_filter: str = "") -> dict:
    """Compute unified health score across all active signal sources.

    Args:
        source_filter: Optional filter -- "api", "mcp", or "" (all).

    Returns:
        Combined health dict with health_score, rating, components,
        and per_source array with individual source health.
    """
    from bannin.llm.tracker import LLMTracker

    tracker = LLMTracker.get()
    per_source: list[dict] = []

    if source_filter != "api":
        _collect_mcp_sources(tracker, per_source)

    if source_filter != "api" and not any(s["type"] == "mcp" for s in per_source):
        _collect_jsonl_fallback(tracker, per_source)

    if source_filter not in ("api", "mcp"):
        _collect_ollama_sources(tracker, per_source)

    if source_filter != "mcp":
        _collect_api_sources(tracker, per_source)

    if per_source:
        return _build_combined(tracker, per_source)
    return tracker.get_health()


def _collect_mcp_sources(tracker: LLMTracker, per_source: list[dict]) -> None:
    """Add per-MCP-session health entries."""
    sessions = get_mcp_sessions()
    for sid, session_data in sessions.items():
        label = session_data.get("client_label", "MCP Session")
        health = tracker.get_health(
            session_fatigue=session_data,
            client_label=label,
        )
        entry = {
            "id": f"mcp-{sid[:8]}",
            "label": f"{label} - MCP",
            "type": "mcp",
            "session_id": sid,
            "health_score": health["health_score"],
            "rating": health["rating"],
            "components": health.get("components", {}),
            "recommendation": health.get("recommendation"),
            "data_source": session_data.get("data_source", "estimated"),
            "session_duration_minutes": session_data.get("session_duration_minutes", 0),
            "total_tool_calls": session_data.get("total_tool_calls", 0),
            "estimated_context_percent": session_data.get("estimated_context_percent", 0),
        }
        real = session_data.get("real_session_data")
        if real:
            entry["real_data"] = _extract_real_data(real)
        per_source.append(entry)


def _collect_jsonl_fallback(tracker: LLMTracker, per_source: list[dict]) -> None:
    """Add health from local JSONL transcript when no MCP push is active."""
    try:
        from bannin.llm.claude_session import ClaudeSessionReader

        rd = ClaudeSessionReader.get().get_real_health_data()
        if rd and rd.get("context_tokens", 0) > 0:
            ctx_pct = rd.get("context_percent", 0)
            duration_s = rd.get("session_duration_seconds", 0)
            session_data = {
                "session_fatigue": 0,
                "context_pressure": 0,
                "estimated_context_percent": ctx_pct,
                "session_duration_minutes": round(duration_s / 60, 1),
                "total_tool_calls": rd.get("total_tool_uses", 0),
                "data_source": "real",
                "real_session_data": rd,
            }
            label = "Claude Code"
            health = tracker.get_health(
                session_fatigue=session_data,
                client_label=label,
            )
            per_source.append({
                "id": "local-jsonl",
                "label": f"{label} - MCP",
                "type": "mcp",
                "health_score": health["health_score"],
                "rating": health["rating"],
                "components": health.get("components", {}),
                "recommendation": health.get("recommendation"),
                "data_source": "real",
                "session_duration_minutes": round(duration_s / 60, 1),
                "total_tool_calls": rd.get("total_tool_uses", 0),
                "estimated_context_percent": ctx_pct,
                "real_data": _extract_real_data(rd),
            })
    except Exception:
        logger.debug("JSONL fallback health computation failed", exc_info=True)


def _collect_ollama_sources(tracker: LLMTracker, per_source: list[dict]) -> None:
    """Add Ollama local LLM health if available."""
    try:
        from bannin.llm.ollama import OllamaMonitor

        ollama = OllamaMonitor.get().get_health()
        if ollama.get("available") and ollama.get("models"):
            vram_pressure = ollama.get("vram_pressure")
            model_names = [m.get("name", "") for m in ollama.get("models", [])[:3]]
            label = "Ollama - " + ", ".join(model_names) if model_names else "Ollama"
            health = tracker.get_health(
                vram_pressure=vram_pressure,
            )
            per_source.append({
                "id": "ollama",
                "label": label,
                "type": "ollama",
                "health_score": health["health_score"],
                "rating": health["rating"],
                "components": health.get("components", {}),
                "recommendation": health.get("recommendation"),
            })
    except Exception:
        logger.debug("Ollama health computation failed", exc_info=True)


def _collect_api_sources(tracker: LLMTracker, per_source: list[dict]) -> None:
    """Add API tracker health if there are tracked calls."""
    api_summary = tracker.get_summary()
    if api_summary.get("total_calls", 0) > 0:
        health = tracker.get_health()
        per_source.append({
            "id": "api",
            "label": "LLM API",
            "type": "api",
            "health_score": health["health_score"],
            "rating": health["rating"],
            "components": health.get("components", {}),
            "recommendation": health.get("recommendation"),
        })


def _build_combined(tracker: LLMTracker, per_source: list[dict]) -> dict:
    """Build combined health result from per-source data (worst-of).

    Uses the worst source's recommendation directly rather than
    recomputing from tracker.get_health(), which would not reflect
    the per-source signals that drove the worst score.
    """
    worst_source = min(per_source, key=lambda s: s["health_score"])
    worst_score = worst_source["health_score"]

    # Merge all components from per-source entries
    all_components: dict = {}
    for src in per_source:
        for key, comp in src.get("components", {}).items():
            # Keep the worst-scoring version of each component
            if key not in all_components or comp.get("score", 100) < all_components[key].get("score", 100):
                all_components[key] = comp

    combined = {
        "health_score": worst_score,
        "rating": _score_to_rating(worst_score),
        "source": f"Combined ({len(per_source)} source{'s' if len(per_source) != 1 else ''})",
        "components": all_components,
        "recommendation": worst_source.get("recommendation"),
        "per_source": per_source,
    }
    return combined


def _score_to_rating(score: float) -> str:
    """Convert numeric score to rating string.

    Imports thresholds from health.py's config loader to stay in sync
    with the canonical threshold definitions.
    """
    from bannin.llm.health import _load_thresholds

    thresholds = _load_thresholds()
    if score >= thresholds.get("excellent", 90):
        return "excellent"
    if score >= thresholds.get("good", 70):
        return "good"
    if score >= thresholds.get("fair", 50):
        return "fair"
    if score >= thresholds.get("poor", 30):
        return "poor"
    return "critical"


def _extract_real_data(rd: dict) -> dict:
    """Extract standardized real data subset from JSONL health data."""
    return {
        "model": rd.get("model"),
        "context_tokens": rd.get("context_tokens", 0),
        "context_window": rd.get("context_window", 200000),
        "context_percent": rd.get("context_percent", 0),
        "total_output_tokens": rd.get("total_output_tokens", 0),
        "total_messages": rd.get("total_messages", 0),
        "total_tool_uses": rd.get("total_tool_uses", 0),
        "cache_hit_rate": rd.get("cache_hit_rate", 0),
        "session_duration_seconds": rd.get("session_duration_seconds", 0),
        "api_calls": rd.get("api_calls", 0),
        "context_growth_rate": rd.get("context_growth_rate"),
    }
