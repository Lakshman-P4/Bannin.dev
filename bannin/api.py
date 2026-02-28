"""Bannin agent REST API -- all endpoints served at localhost:8420.

FastAPI application with system metrics, intelligence, LLM health,
analytics, chatbot, and MCP session management endpoints.
"""

from __future__ import annotations

import asyncio
import json
import platform
import threading
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from bannin.log import logger
from bannin.core.collector import get_all_metrics
from bannin.core.gpu import get_gpu_metrics, is_gpu_available
from bannin.core.process import (
    get_process_count, get_top_processes,
    get_grouped_processes, get_resource_breakdown,
    is_scanner_ready,
)
from bannin.platforms.detector import detect_platform
from bannin.routes import emit_event as _emit, error_response

_start_time: float = 0.0
_detected_platform = detect_platform()

try:
    _DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
except FileNotFoundError:
    _DASHBOARD_HTML = "<h1>Bannin</h1><p>Dashboard file not found. API available at /health</p>"


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

def _on_startup() -> None:
    """Start background services and pre-warm process cache on boot."""
    global _start_time
    _start_time = time.time()

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

    from bannin.llm.ollama import OllamaMonitor
    OllamaMonitor.get().start()

    try:
        import os
        from bannin.llm.claude_session import ClaudeSessionReader
    except ImportError:
        logger.debug("JSONL session reader unavailable (claude_session module not importable)")
    else:
        try:
            reader = ClaudeSessionReader.get()
            reader.start(cwd=os.getcwd())
        except Exception:
            logger.debug("JSONL session reader not started (may not be in a Claude Code session)")

    threading.Thread(target=_prewarm, daemon=True).start()


def _on_shutdown() -> None:
    """Stop background services (reverse start order), flush pipeline, close store."""
    # Stop background services before flushing the pipeline so their last
    # events can still be written.
    try:
        from bannin.llm.claude_session import ClaudeSessionReader
        ClaudeSessionReader.get().stop()
    except Exception:
        logger.debug("Failed to stop ClaudeSessionReader on shutdown")

    try:
        from bannin.llm.ollama import OllamaMonitor
        OllamaMonitor.get().stop()
    except Exception:
        logger.debug("Failed to stop OllamaMonitor on shutdown")

    try:
        from bannin.intelligence.history import MetricHistory
        MetricHistory.get().stop()
    except Exception:
        logger.debug("Failed to stop MetricHistory on shutdown")

    try:
        from bannin.core.process import stop_background_scanner
        stop_background_scanner()
    except Exception:
        logger.debug("Failed to stop background scanner on shutdown")

    # Emit final event and flush pipeline
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
        logger.warning("Failed to emit session_stop event on shutdown", exc_info=True)

    try:
        from bannin.analytics.store import AnalyticsStore
        AnalyticsStore.get().close_all()
    except Exception:
        logger.debug("Failed to close analytics store connections on shutdown")


_relay_client = None


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _relay_client
    _on_startup()

    # Start relay client if configured
    import os
    relay_key = os.environ.get("BANNIN_RELAY_KEY", "")
    relay_url = os.environ.get("BANNIN_RELAY_URL", "")
    if relay_key:
        try:
            from bannin.relay import RelayClient
            _relay_client = RelayClient(relay_url, relay_key)
            await _relay_client.start()
        except Exception:
            logger.warning("Failed to start relay client", exc_info=True)

    yield

    # Stop relay client before shutting down other services
    if _relay_client is not None:
        try:
            await _relay_client.stop()
        except Exception:
            logger.debug("Failed to stop relay client on shutdown")
        _relay_client = None

    _on_shutdown()


def _prewarm() -> None:
    """Start the background process scanner."""
    from bannin.core.process import start_background_scanner
    start_background_scanner(interval=15)


# ---------------------------------------------------------------------------
# App creation + router mounting
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Bannin Agent",
    description="Universal monitoring agent -- system metrics, GPU, processes, cloud notebooks",
    version="0.1.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8420",
        "http://127.0.0.1:8420",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount sub-routers
from bannin.routes.llm import router as llm_router
from bannin.routes.intelligence import router as intelligence_router
from bannin.routes.mcp import router as mcp_router
from bannin.routes.analytics import router as analytics_router
from bannin.routes.actions import router as actions_router

app.include_router(llm_router)
app.include_router(intelligence_router)
app.include_router(mcp_router)
app.include_router(analytics_router)
app.include_router(actions_router)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled exceptions and return structured JSON instead of HTML 500."""
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return error_response(500, "Internal server error")


@app.exception_handler(404)
async def _not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(404, "Not found", f"{request.url.path} does not exist")


# ---------------------------------------------------------------------------
# Core endpoints (kept in api.py)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    """Serve the live monitoring dashboard."""
    _emit("dashboard_view", "agent", "info", "Dashboard viewed")
    return HTMLResponse(content=_DASHBOARD_HTML)


@app.get("/health")
def health() -> dict:
    _emit("health_check", "agent", "info", "Health check polled")
    return {"status": "ok"}


@app.get("/status")
def status() -> dict:
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
def metrics() -> dict:
    data = get_all_metrics()
    data["gpu"] = get_gpu_metrics()
    data["environment"] = _detected_platform
    return data


@app.get("/processes")
def processes(limit: int = Query(default=15, ge=1, le=100)) -> dict:
    return {
        "summary": get_process_count(),
        "top_processes": get_grouped_processes(limit=limit),
        "resource_breakdown": get_resource_breakdown(),
    }


@app.get("/metrics/self")
def metrics_self() -> dict:
    """Report the Bannin agent's own resource footprint."""
    import os
    import psutil

    proc = psutil.Process(os.getpid())
    with proc.oneshot():
        mem = proc.memory_info()
        try:
            cpu = proc.cpu_percent(interval=0.1)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            cpu = 0.0
        threads = proc.num_threads()
        create_time = proc.create_time()

    uptime = time.time() - _start_time

    return {
        "pid": os.getpid(),
        "cpu_percent": round(cpu, 1),
        "memory_rss_mb": round(mem.rss / (1024 * 1024), 1),
        "memory_vms_mb": round(mem.vms / (1024 * 1024), 1),
        "threads": threads,
        "uptime_seconds": round(uptime, 1),
        "create_time": create_time,
    }


@app.get("/platform")
def platform_info() -> dict:
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


# ---------------------------------------------------------------------------
# Server-Sent Events (SSE) stream
# ---------------------------------------------------------------------------

def _sse_event(event_type: str, data: dict) -> str:
    """Format an SSE event string."""
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _collect_fast() -> list[tuple[str, dict]]:
    """Fast-cycle data: metrics + active alerts (every ~3s)."""
    events = []
    try:
        data = get_all_metrics()
        data["gpu"] = get_gpu_metrics()
        data["environment"] = _detected_platform
        events.append(("metrics", data))
    except Exception:
        logger.warning("SSE: failed to collect metrics", exc_info=True)
    try:
        from bannin.intelligence.alerts import ThresholdEngine
        events.append(("alerts", ThresholdEngine.get().get_active_alerts()))
    except Exception:
        logger.warning("SSE: failed to collect alerts", exc_info=True)
    return events


def _collect_medium() -> list[tuple[str, dict]]:
    """Medium-cycle data: processes, tasks, OOM (every ~8s)."""
    events = []
    try:
        events.append(("processes", {
            "summary": get_process_count(),
            "top_processes": get_grouped_processes(limit=15),
            "resource_breakdown": get_resource_breakdown(),
            "scanner_ready": is_scanner_ready(),
        }))
    except Exception:
        logger.warning("SSE: failed to collect processes", exc_info=True)
    try:
        from bannin.intelligence.progress import ProgressTracker
        events.append(("tasks", ProgressTracker.get().get_tasks()))
    except Exception:
        logger.warning("SSE: failed to collect tasks", exc_info=True)
    try:
        from bannin.intelligence.oom import OOMPredictor
        events.append(("oom", OOMPredictor.get().predict()))
    except Exception:
        logger.warning("SSE: failed to collect OOM prediction", exc_info=True)
    return events


def _collect_slow() -> list[tuple[str, dict]]:
    """Slow-cycle data: status, LLM, health, Ollama, etc (every ~15s)."""
    events = []
    try:
        events.append(("status", {
            "agent": "bannin",
            "version": "0.1.0",
            "hostname": platform.node(),
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "gpu_available": is_gpu_available(),
            "environment": _detected_platform,
            "uptime_seconds": round(time.time() - _start_time, 1),
        }))
    except Exception:
        logger.warning("SSE: failed to collect status", exc_info=True)
    try:
        from bannin.llm.tracker import LLMTracker
        events.append(("llm_usage", LLMTracker.get().get_summary()))
    except Exception:
        logger.warning("SSE: failed to collect LLM usage", exc_info=True)
    try:
        from bannin.intelligence.history import MetricHistory
        history = MetricHistory.get()
        readings = history.get_memory_history(last_n_minutes=5)
        events.append(("memory_history", {
            "readings": readings,
            "count": len(readings),
            "period_minutes": 5,
            "total_readings_stored": history.reading_count,
        }))
    except Exception:
        logger.warning("SSE: failed to collect memory history", exc_info=True)
    try:
        from bannin.llm.aggregator import compute_health
        events.append(("health", compute_health()))
    except Exception:
        logger.warning("SSE: failed to collect health", exc_info=True)
    try:
        from bannin.llm.ollama import OllamaMonitor
        events.append(("ollama", OllamaMonitor.get().get_health()))
    except Exception:
        logger.warning("SSE: failed to collect Ollama", exc_info=True)
    try:
        from bannin.intelligence.recommendations import build_recommendation_snapshot, generate_recommendations
        snapshot = build_recommendation_snapshot()
        events.append(("recommendations", {"recommendations": generate_recommendations(snapshot)}))
    except Exception:
        logger.warning("SSE: failed to collect recommendations", exc_info=True)
    try:
        from bannin.llm.connections import LLMConnectionScanner
        events.append(("connections", {"connections": LLMConnectionScanner.get().get_connections()}))
    except Exception:
        logger.warning("SSE: failed to collect connections", exc_info=True)
    return events


@app.get("/stream")
async def stream(request: Request) -> StreamingResponse:
    """Server-Sent Events endpoint -- pushes all dashboard data over a single connection."""

    async def event_generator() -> AsyncGenerator[str, None]:
        _emit("sse_connect", "agent", "info", "SSE client connected")
        yield ": connected\n\n"

        last_fast = 0.0
        last_medium = 0.0
        last_slow = 0.0

        try:
            while True:
                if await request.is_disconnected():
                    break

                now = time.time()
                events: list[tuple[str, dict]] = []

                if now - last_fast >= 3:
                    last_fast = now
                    events.extend(await asyncio.to_thread(_collect_fast))

                if now - last_medium >= 8:
                    last_medium = now
                    events.extend(await asyncio.to_thread(_collect_medium))

                if now - last_slow >= 15:
                    last_slow = now
                    events.extend(await asyncio.to_thread(_collect_slow))

                for event_type, data in events:
                    yield _sse_event(event_type, data)

                await asyncio.sleep(1)
        finally:
            _emit("sse_disconnect", "agent", "info", "SSE client disconnected")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
