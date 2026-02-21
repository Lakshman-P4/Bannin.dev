"""Bannin MCP Server implementation.

Exposes Bannin monitoring data as MCP tools for AI coding tools
(Claude Code, Cursor, Windsurf) via stdio transport.

Tools:
    get_system_metrics    - Full system snapshot (CPU, RAM, disk, network, GPU)
    get_running_processes - Top processes by CPU/memory usage
    predict_oom           - OOM prediction for RAM and GPU
    get_training_status   - Active/completed/stalled tracked tasks with ETAs
    get_active_alerts     - Currently firing threshold alerts
"""

import json
import os
import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bannin")

# Known MCP client exe names -> display label
# Note: claude.exe can be either Claude Desktop or Claude Code CLI.
# We differentiate by checking if the exe path contains .local\bin (Claude Code CLI).
_CLIENT_EXE_MAP = {
    "code": "Claude Code (VS Code)",
    "code.exe": "Claude Code (VS Code)",
    "cursor": "Cursor",
    "cursor.exe": "Cursor",
    "windsurf": "Windsurf",
    "windsurf.exe": "Windsurf",
    "zed": "Zed",
    "zed.exe": "Zed",
}


def _detect_parent_client() -> str:
    """Walk the process tree to detect which MCP client launched this server."""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        for _ in range(10):
            proc = proc.parent()
            if proc is None:
                break
            name = (proc.name() or "").lower()
            if name in _CLIENT_EXE_MAP:
                return _CLIENT_EXE_MAP[name]
            # claude.exe: differentiate CLI (Claude Code) from Desktop app
            if name in ("claude", "claude.exe"):
                try:
                    exe_path = (proc.exe() or "").lower()
                    # Claude Code CLI installs to .local/bin or AppData
                    if ".local" in exe_path or "appdata" in exe_path:
                        return "Claude Code"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                # Check cmdline for additional hints
                try:
                    cmdline = " ".join(proc.cmdline()).lower()
                    if "code" in cmdline:
                        return "Claude Code"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                return "Claude Desktop"
            # Fallback cmdline checks
            try:
                cmdline = " ".join(proc.cmdline()).lower()
                if "cursor" in cmdline:
                    return "Cursor"
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
    except Exception:
        pass
    return "Unknown MCP Client"


def _record_tool_call(tool_name: str, response_bytes: int = 0):
    """Record a tool call locally. Background pusher handles agent sync."""
    try:
        from bannin.mcp.session import MCPSessionTracker
        MCPSessionTracker.get().record_tool_call(tool_name, response_bytes=response_bytes)
    except Exception:
        pass


def _record_and_return(tool_name: str, result: str) -> str:
    """Record a tool call with measured response size and return the result."""
    _record_tool_call(tool_name, response_bytes=len(result.encode("utf-8")))
    return result


@mcp.tool()
def get_system_metrics() -> str:
    """Get a full system metrics snapshot including CPU, RAM, disk, network, and GPU.

    Returns JSON with: cpu (percent, per_core, count, frequency),
    memory (total/used/available_gb, percent), disk (total/used/free_gb, percent),
    network (bytes sent/received), gpu (list with VRAM, utilization, temperature).

    Use this to check overall system health before spawning heavy tasks.
    """
    from bannin.core.collector import get_all_metrics
    from bannin.core.gpu import get_gpu_metrics

    data = get_all_metrics()
    data["gpu"] = get_gpu_metrics()
    return _record_and_return("get_system_metrics", json.dumps(data, default=str))


@mcp.tool()
def get_running_processes(limit: int = 10) -> str:
    """Get the top processes by CPU and memory usage.

    Args:
        limit: Maximum number of processes to return (default 10).

    Returns JSON with process list (name, category, cpu_percent, memory_mb,
    instance_count) and a summary of total/running/sleeping counts.
    Process names are friendly (e.g., "Google Chrome", "VS Code", "Bannin Agent").

    Use this to see what is consuming resources on the machine.
    """
    from bannin.core.process import get_process_count, get_grouped_processes

    result = {
        "summary": get_process_count(),
        "top_processes": get_grouped_processes(limit=limit),
    }
    return _record_and_return("get_running_processes", json.dumps(result, default=str))


@mcp.tool()
def predict_oom() -> str:
    """Predict out-of-memory events based on memory usage trends.

    Analyzes RAM and GPU memory growth rates using linear regression.
    Returns predictions with confidence scores, time-to-exhaustion
    estimates, and severity levels (ok, warning, critical).

    Requires the Bannin agent to have been running for at least 1 minute
    to accumulate enough data points. Use this before starting
    memory-intensive operations or when you suspect a memory leak.
    """
    from bannin.intelligence.oom import OOMPredictor

    predictor = OOMPredictor()
    return _record_and_return("predict_oom", json.dumps(predictor.predict(), default=str))


@mcp.tool()
def get_training_status() -> str:
    """Get the status of all tracked tasks (training runs, progress bars, etc).

    Returns JSON with active_tasks, completed_tasks, stalled_tasks.
    Each task includes: name, percent complete, elapsed time, ETA,
    and status (running/completed/stalled).

    Tasks are detected from tqdm progress bars and stdout patterns
    (e.g., 'Epoch 3/10') when running inside bannin.watch().

    Use this to check on long-running training jobs or batch processes.
    """
    from bannin.intelligence.progress import ProgressTracker

    return _record_and_return("get_training_status", json.dumps(ProgressTracker.get().get_tasks(), default=str))


@mcp.tool()
def get_active_alerts() -> str:
    """Get currently active monitoring alerts.

    Returns JSON with active alerts, each containing: id, severity,
    message, value, threshold, and fired_at timestamp.

    Severity levels: info, warning, critical.
    Examples: 'RAM at 92%', 'GPU VRAM critical', 'Colab session expiring'.

    Use this to quickly check if anything needs attention.
    """
    from bannin.intelligence.alerts import ThresholdEngine

    return _record_and_return("get_active_alerts", json.dumps(ThresholdEngine.get().get_active_alerts(), default=str))


@mcp.tool()
def check_context_health() -> str:
    """Check AI conversation health including context degradation and session fatigue.

    Returns a unified health score (0-100) combining:
    - Context window usage and model-specific danger zones
    - MCP session fatigue (tool call patterns, session duration)
    - Ollama VRAM pressure (if local models are running)
    - Latency and cost trends (if API calls are tracked)

    The AI can use this to detect its own cognitive degradation.
    When health drops below 50, consider summarizing and starting fresh.

    Use this periodically during long sessions to monitor quality.
    """
    from bannin.llm.tracker import LLMTracker
    from bannin.mcp.session import MCPSessionTracker

    session_fatigue = None
    vram_pressure = None

    try:
        session_fatigue = MCPSessionTracker.get().get_session_health()
    except Exception:
        pass

    try:
        from bannin.llm.ollama import OllamaMonitor
        ollama = OllamaMonitor.get().get_health()
        if ollama.get("available"):
            vram_pressure = ollama.get("vram_pressure")
    except Exception:
        pass

    tracker = LLMTracker.get()
    health = tracker.get_health(
        session_fatigue=session_fatigue,
        vram_pressure=vram_pressure,
    )
    return _record_and_return("check_context_health", json.dumps(health, default=str))


@mcp.tool()
def get_recommendations() -> str:
    """Get L2 actionable recommendations based on cross-signal analysis.

    Analyzes system metrics, LLM health, Ollama status, MCP session,
    and platform constraints to produce prioritized suggestions.

    Each recommendation includes priority (1=critical to 5=info),
    category, human-readable message, and suggested action.

    Use this to get specific, actionable advice when something needs attention.
    """
    from bannin.intelligence.recommendations import build_recommendation_snapshot, generate_recommendations

    snapshot = build_recommendation_snapshot()
    recs = generate_recommendations(snapshot)
    return _record_and_return("get_recommendations", json.dumps({"recommendations": recs}, default=str))


@mcp.tool()
def query_history(event_type: str = "", severity: str = "", since: str = "1h", limit: int = 50) -> str:
    """Query Bannin's persistent event history.

    Args:
        event_type: Filter by type (alert, metric_snapshot, llm_call, session_start, etc).
        severity: Filter by severity (info, warning, critical).
        since: How far back to look (e.g., "30m", "2h", "7d"). Default "1h".
        limit: Max events to return (default 50).

    Returns stored events matching the filters, newest first.
    Use this to answer "what happened while I was away?" or investigate past alerts.
    """
    from bannin.analytics.store import AnalyticsStore
    import time as _time

    since_ts = None
    if since:
        s = since.strip().lower()
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
        for suffix, mult in multipliers.items():
            if s.endswith(suffix):
                try:
                    since_ts = _time.time() - (float(s[:-1]) * mult)
                except ValueError:
                    pass
                break

    events = AnalyticsStore.get().query(
        event_type=event_type or None,
        severity=severity or None,
        since=since_ts,
        limit=limit,
    )
    result = json.dumps({"events": events, "count": len(events)}, default=str)
    return _record_and_return("query_history", result)


@mcp.tool()
def search_events(query: str, limit: int = 30) -> str:
    """Full-text search across all stored Bannin events.

    Args:
        query: Search term (e.g., "RAM", "OOM", "Chrome", "model loaded").
        limit: Max results (default 30).

    Searches event messages using FTS5 full-text search.
    Use this to find specific events like "show me every OOM warning this week".
    """
    from bannin.analytics.store import AnalyticsStore

    results = AnalyticsStore.get().search(query, limit=limit)
    return _record_and_return("search_events", json.dumps({"results": results, "count": len(results)}, default=str))


def _start_session_pusher():
    """Background thread that pushes MCP session data to the agent periodically."""
    import threading
    import time
    import urllib.request

    def _push_loop():
        # Wait briefly for the agent to be ready
        time.sleep(2)
        from bannin.mcp.session import MCPSessionTracker
        tracker = MCPSessionTracker.get()

        while True:
            try:
                payload = tracker.get_push_payload()
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    "http://localhost:8420/mcp/session",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=2)
            except Exception:
                pass
            time.sleep(10)

    t = threading.Thread(target=_push_loop, daemon=True)
    t.start()


def serve():
    """Start the Bannin MCP server with stdio transport."""
    # Detect parent client before anything else
    from bannin.mcp.session import MCPSessionTracker
    tracker = MCPSessionTracker.get()
    client_label = _detect_parent_client()
    tracker.set_client_label(client_label)
    print(f"Bannin MCP: detected client '{client_label}', session {tracker.session_id[:8]}...", file=sys.stderr)

    # Analytics store + pipeline
    from bannin.analytics.store import AnalyticsStore
    from bannin.analytics.pipeline import EventPipeline
    AnalyticsStore.get()
    pipeline = EventPipeline.get()
    pipeline.start()

    # Start intelligence modules so predictions and alerts work
    from bannin.intelligence.history import MetricHistory
    MetricHistory.get().start()

    # Ollama monitor (zero-config)
    from bannin.llm.ollama import OllamaMonitor
    OllamaMonitor.get().start()

    # Start background process scanner so grouped process data is available
    from bannin.core.process import start_background_scanner
    start_background_scanner(interval=30)

    # Start Claude JSONL session reader for real token data
    try:
        from bannin.llm.claude_session import ClaudeSessionReader
        reader = ClaudeSessionReader.get()
        reader.start(cwd=os.getcwd())
        sf = reader.session_file
        print(f"Bannin MCP: JSONL reader started ({sf.name if sf else 'no file found'})", file=sys.stderr)
    except Exception as e:
        print(f"Bannin MCP: JSONL reader skipped ({e})", file=sys.stderr)

    # Push session data to agent immediately and every 5 seconds
    _start_session_pusher()

    print("Bannin MCP server starting...", file=sys.stderr)
    mcp.run(transport="stdio")
