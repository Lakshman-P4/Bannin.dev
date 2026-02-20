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
import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("bannin")


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
    return json.dumps(data, default=str)


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
    return json.dumps(result, default=str)


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
    return json.dumps(predictor.predict(), default=str)


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

    return json.dumps(ProgressTracker.get().get_tasks(), default=str)


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

    return json.dumps(ThresholdEngine.get().get_active_alerts(), default=str)


def serve():
    """Start the Bannin MCP server with stdio transport."""
    # Start intelligence modules so predictions and alerts work
    from bannin.intelligence.history import MetricHistory
    MetricHistory.get().start()
    # Start background process scanner so grouped process data is available
    from bannin.core.process import start_background_scanner
    start_background_scanner(interval=15)
    print("Bannin MCP server starting...", file=sys.stderr)
    mcp.run(transport="stdio")
