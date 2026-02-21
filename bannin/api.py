import platform
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from bannin.core.collector import get_all_metrics
from bannin.core.gpu import get_gpu_metrics, is_gpu_available
from bannin.core.process import (
    get_process_count, get_top_processes,
    get_grouped_processes, get_resource_breakdown,
)
from bannin.platforms.detector import detect_platform

_start_time = time.time()
_detected_platform = detect_platform()

try:
    _DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
except FileNotFoundError:
    _DASHBOARD_HTML = "<h1>Bannin</h1><p>Dashboard file not found. API available at /health</p>"

app = FastAPI(
    title="Bannin Agent",
    description="Universal monitoring agent -- system metrics, GPU, processes, cloud notebooks",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup():
    """Start background services and pre-warm process cache on boot."""
    # Analytics store + pipeline (must start before anything emits events)
    from bannin.analytics.store import AnalyticsStore
    from bannin.analytics.pipeline import EventPipeline
    AnalyticsStore.get()
    pipeline = EventPipeline.get()
    pipeline.start()
    pipeline.emit({
        "type": "session_start",
        "source": "agent",
        "severity": "info",
        "message": "Bannin agent started",
        "data": {"port": 8420},
    })

    from bannin.intelligence.history import MetricHistory
    MetricHistory.get().start()

    # Ollama monitor (zero-config, auto-detects)
    from bannin.llm.ollama import OllamaMonitor
    OllamaMonitor.get().start()

    # Start JSONL session reader so the agent has real token data
    # even when the MCP server isn't running (standalone dashboard use)
    try:
        import os
        from bannin.llm.claude_session import ClaudeSessionReader
        reader = ClaudeSessionReader.get()
        reader.start(cwd=os.getcwd())
    except Exception:
        pass

    # Pre-warm process data in background so first request is instant
    import threading
    threading.Thread(target=_prewarm, daemon=True).start()


@app.on_event("shutdown")
def _on_shutdown():
    """Emit session stop event and flush pipeline."""
    try:
        from bannin.analytics.pipeline import EventPipeline
        pipeline = EventPipeline.get()
        pipeline.emit({
            "type": "session_stop",
            "source": "agent",
            "severity": "info",
            "message": "Bannin agent stopped",
            "data": {},
        })
        pipeline.stop()
    except Exception:
        pass


def _prewarm():
    """Start the background process scanner."""
    from bannin.core.process import start_background_scanner
    start_background_scanner(interval=30)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    """Serve the live monitoring dashboard."""
    return HTMLResponse(content=_DASHBOARD_HTML)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    return {
        "agent": "bannin",
        "version": "0.1.0",
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "gpu_available": is_gpu_available(),
        "environment": _detected_platform,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@app.get("/metrics")
def metrics():
    data = get_all_metrics()
    data["gpu"] = get_gpu_metrics()
    data["environment"] = _detected_platform
    return data


@app.get("/processes")
def processes(limit: int = 15):
    return {
        "summary": get_process_count(),
        "top_processes": get_grouped_processes(limit=limit),
        "resource_breakdown": get_resource_breakdown(),
    }


@app.get("/platform")
def platform_info():
    """Platform-specific monitoring for Colab, Kaggle, or local."""
    if _detected_platform == "colab":
        from bannin.platforms.colab import get_colab_metrics
        return get_colab_metrics()
    elif _detected_platform == "kaggle":
        from bannin.platforms.kaggle import get_kaggle_metrics
        return get_kaggle_metrics()
    else:
        return {
            "platform": "local",
            "message": "Running on a local machine. Colab/Kaggle-specific monitoring is not applicable.",
        }


@app.get("/llm/usage")
def llm_usage():
    """LLM token and cost tracking summary."""
    from bannin.llm.tracker import LLMTracker
    tracker = LLMTracker.get()
    return tracker.get_summary()


@app.get("/llm/calls")
def llm_calls(limit: int = 20):
    """Recent LLM API calls."""
    from bannin.llm.tracker import LLMTracker
    tracker = LLMTracker.get()
    return {"calls": tracker.get_calls(limit=limit)}


@app.get("/llm/context")
def llm_context(model: str = "", tokens: int = 0):
    """Context window usage prediction for a model."""
    from bannin.llm.tracker import LLMTracker
    tracker = LLMTracker.get()
    if not model:
        return {"error": "Provide ?model=gpt-4o&tokens=50000"}
    return tracker.get_context_usage(model, tokens)


@app.get("/llm/latency")
def llm_latency(model: str = ""):
    """Latency trend analysis."""
    from bannin.llm.tracker import LLMTracker
    tracker = LLMTracker.get()
    return tracker.get_latency_trend(model=model or None)


@app.get("/predictions/oom")
def predictions_oom():
    """Predict out-of-memory events based on memory usage trends."""
    from bannin.intelligence.oom import OOMPredictor
    predictor = OOMPredictor()
    return predictor.predict()


@app.get("/history/memory")
def history_memory(minutes: float = 5):
    """Memory usage history over the last N minutes (for graphing and predictions)."""
    from bannin.intelligence.history import MetricHistory
    history = MetricHistory.get()
    readings = history.get_memory_history(last_n_minutes=minutes)
    return {
        "readings": readings,
        "count": len(readings),
        "period_minutes": minutes,
        "total_readings_stored": history.reading_count,
    }


@app.get("/alerts")
def alerts(limit: int = 50):
    """Full alert history for this session."""
    from bannin.intelligence.alerts import ThresholdEngine
    return ThresholdEngine.get().get_alerts(limit=limit)


@app.get("/alerts/active")
def alerts_active():
    """Currently active alerts (fired within their cooldown window)."""
    from bannin.intelligence.alerts import ThresholdEngine
    return ThresholdEngine.get().get_active_alerts()


@app.get("/tasks")
def tasks():
    """Tracked tasks — training progress and ETAs."""
    from bannin.intelligence.progress import ProgressTracker
    return ProgressTracker.get().get_tasks()


@app.get("/tasks/{task_id}")
def task_detail(task_id: str):
    """Get details of a single tracked task."""
    from bannin.intelligence.progress import ProgressTracker
    task = ProgressTracker.get().get_task(task_id)
    if task is None:
        return {"error": f"Task '{task_id}' not found"}
    return task


@app.get("/summary")
def summary():
    """Plain-English system health summary for non-technical users."""
    from bannin.intelligence.summary import generate_summary
    return generate_summary()


# MCP session data pushed from MCP server processes (keyed by session_id)
_mcp_sessions: dict[str, dict] = {}
_mcp_session_lock = __import__("threading").Lock()
_MCP_SESSION_TTL = 60  # seconds before a session is considered expired


def _expire_sessions():
    """Remove sessions that haven't pushed data within TTL. Caller holds lock."""
    now = __import__("time").time()
    expired = [sid for sid, data in _mcp_sessions.items()
               if now - data.get("_last_seen", 0) > _MCP_SESSION_TTL]
    for sid in expired:
        del _mcp_sessions[sid]


def get_mcp_sessions() -> dict[str, dict]:
    """Get all live MCP sessions (keyed by session_id). Expires stale sessions."""
    with _mcp_session_lock:
        _expire_sessions()
        return {sid: {k: v for k, v in data.items() if not k.startswith("_")}
                for sid, data in _mcp_sessions.items()}


def get_mcp_session_data() -> dict | None:
    """Backwards-compat: get the worst (most fatigued) MCP session, or None."""
    sessions = get_mcp_sessions()
    if not sessions:
        return None
    # Return the session with the highest fatigue (worst health)
    worst = max(sessions.values(), key=lambda s: s.get("session_fatigue", 0))
    return worst


@app.post("/mcp/session")
def mcp_session_update(body: dict):
    """Receive MCP session health data pushed from an MCP server process."""
    session_id = body.get("session_id")
    if not session_id:
        # Legacy push without session_id -- use a synthetic key
        session_id = "_legacy"
    with _mcp_session_lock:
        body["_last_seen"] = __import__("time").time()
        _mcp_sessions[session_id] = body
    return {"status": "ok"}


@app.get("/mcp/sessions")
def mcp_sessions_list():
    """All live MCP sessions with their health data."""
    sessions = get_mcp_sessions()
    return {
        "sessions": list(sessions.values()),
        "count": len(sessions),
    }


@app.get("/llm/health")
def llm_health(source: str = ""):
    """Unified conversation health score across all signal sources.

    Returns combined score + per_source array with individual health per MCP session / Ollama / API.
    """
    from bannin.llm.tracker import LLMTracker
    from bannin.llm.health import calculate_health_score

    tracker = LLMTracker.get()
    per_source: list[dict] = []

    # --- Per-MCP-session health ---
    if source != "api":
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
            # Include real JSONL data when available
            real = session_data.get("real_session_data")
            if real:
                entry["real_data"] = {
                    "model": real.get("model"),
                    "context_tokens": real.get("context_tokens", 0),
                    "context_window": real.get("context_window", 200000),
                    "context_percent": real.get("context_percent", 0),
                    "total_output_tokens": real.get("total_output_tokens", 0),
                    "total_messages": real.get("total_messages", 0),
                    "total_tool_uses": real.get("total_tool_uses", 0),
                    "cache_hit_rate": real.get("cache_hit_rate", 0),
                    "session_duration_seconds": real.get("session_duration_seconds", 0),
                    "api_calls": real.get("api_calls", 0),
                    "context_growth_rate": real.get("context_growth_rate"),
                }
            per_source.append(entry)

    # --- Local JSONL fallback: show health from JSONL even without MCP push ---
    if source != "api" and not any(s["type"] == "mcp" for s in per_source):
        try:
            from bannin.llm.claude_session import ClaudeSessionReader
            rd = ClaudeSessionReader.get().get_real_health_data()
            if rd and rd.get("context_tokens", 0) > 0:
                # Build a synthetic session_data dict for health calculation
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
                entry = {
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
                    "real_data": {
                        "model": rd.get("model"),
                        "context_tokens": rd.get("context_tokens", 0),
                        "context_window": rd.get("context_window", 200000),
                        "context_percent": ctx_pct,
                        "total_output_tokens": rd.get("total_output_tokens", 0),
                        "total_messages": rd.get("total_messages", 0),
                        "total_tool_uses": rd.get("total_tool_uses", 0),
                        "cache_hit_rate": rd.get("cache_hit_rate", 0),
                        "session_duration_seconds": duration_s,
                        "api_calls": rd.get("api_calls", 0),
                        "context_growth_rate": rd.get("context_growth_rate"),
                    },
                }
                per_source.append(entry)
        except Exception:
            pass

    # --- Ollama health ---
    if source != "api" and source != "mcp":
        try:
            from bannin.llm.ollama import OllamaMonitor
            ollama = OllamaMonitor.get().get_health()
            if ollama.get("available") and ollama.get("models"):
                vram_pressure = ollama.get("vram_pressure")
                inference_trend = ollama.get("inference_trend")
                model_names = [m.get("name", "") for m in ollama.get("models", [])[:3]]
                label = "Ollama - " + ", ".join(model_names) if model_names else "Ollama"
                health = tracker.get_health(
                    vram_pressure=vram_pressure,
                    inference_trend=inference_trend,
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
            pass

    # --- API tracker health (if there are tracked calls) ---
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

    # --- Combined score (worst-of) ---
    if per_source:
        worst_score = min(s["health_score"] for s in per_source)
        combined_health = tracker.get_health(
            session_fatigue=get_mcp_session_data(),
            vram_pressure=_get_ollama_vram(),
        )
        combined_health["health_score"] = worst_score
        combined_health["rating"] = _score_to_rating(worst_score)
        combined_health["source"] = f"Combined ({len(per_source)} source{'s' if len(per_source) != 1 else ''})"
        combined_health["per_source"] = per_source
        return combined_health
    else:
        # No active sources
        return tracker.get_health()


def _get_ollama_vram() -> float | None:
    """Helper to get Ollama VRAM pressure, or None."""
    try:
        from bannin.llm.ollama import OllamaMonitor
        ollama = OllamaMonitor.get().get_health()
        if ollama.get("available"):
            return ollama.get("vram_pressure")
    except Exception:
        pass
    return None


def _score_to_rating(score: float) -> str:
    """Convert numeric score to rating string."""
    if score >= 90:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 50:
        return "fair"
    if score >= 30:
        return "poor"
    return "critical"


@app.get("/recommendations")
def recommendations():
    """L2 actionable recommendations from cross-signal analysis."""
    from bannin.intelligence.recommendations import build_recommendation_snapshot, generate_recommendations
    snapshot = build_recommendation_snapshot()
    return {"recommendations": generate_recommendations(snapshot)}


@app.get("/llm/connections")
def llm_connections():
    """Auto-detected LLM tools and connections on this system."""
    from bannin.llm.connections import LLMConnectionScanner
    return {"connections": LLMConnectionScanner.get().get_connections()}


@app.get("/ollama")
def ollama_status():
    """Ollama local LLM status -- loaded models, VRAM, availability."""
    from bannin.llm.ollama import OllamaMonitor
    return OllamaMonitor.get().get_health()


@app.get("/analytics/stats")
def analytics_stats():
    """Analytics store statistics -- event counts, DB size, time range."""
    from bannin.analytics.store import AnalyticsStore
    return AnalyticsStore.get().get_stats()


@app.get("/analytics/events")
def analytics_events(type: str = "", severity: str = "", since: str = "", limit: int = 100):
    """Query stored analytics events with optional filters."""
    from bannin.analytics.store import AnalyticsStore
    import time as _time

    since_ts = None
    if since:
        since_ts = _parse_since(since)

    return {
        "events": AnalyticsStore.get().query(
            event_type=type or None,
            severity=severity or None,
            since=since_ts,
            limit=limit,
        )
    }


@app.get("/analytics/search")
def analytics_search(q: str = "", limit: int = 50):
    """Full-text search across stored events."""
    from bannin.analytics.store import AnalyticsStore
    if not q:
        return {"error": "Provide ?q=search+term"}
    return {"results": AnalyticsStore.get().search(q, limit=limit)}


@app.get("/analytics/timeline")
def analytics_timeline(since: str = "", limit: int = 200):
    """Event timeline, newest first."""
    from bannin.analytics.store import AnalyticsStore
    since_ts = _parse_since(since) if since else None
    return {"timeline": AnalyticsStore.get().get_timeline(since=since_ts, limit=limit)}


@app.post("/chat")
def chat_endpoint(body: dict):
    """Chatbot endpoint -- natural language system health assistant."""
    from bannin.intelligence.chat import chat
    message = body.get("message", "")
    return chat(message)


def _parse_since(since_str: str) -> float | None:
    """Parse human time strings like '1h', '30m', '7d' into epoch timestamp."""
    import time as _time
    s = since_str.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            try:
                val = float(s[:-1])
                return _time.time() - (val * mult)
            except ValueError:
                return None
    try:
        return float(s)
    except ValueError:
        return None
