from __future__ import annotations

__version__ = "0.1.0"

import threading
from types import TracebackType

from bannin.core.collector import get_all_metrics
from bannin.llm.wrapper import wrap
from bannin.llm.tracker import track


class Bannin:
    """Main Bannin agent — collects metrics and exposes API."""

    def __init__(self, port: int = 8420) -> None:
        self._port = port
        self._server_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        """Start the agent API server in a background thread."""
        import uvicorn
        from bannin.api import app

        with self._lock:
            if self._running:
                return
            self._running = True
            self._server_thread = threading.Thread(
                target=uvicorn.run,
                kwargs={"app": app, "host": "127.0.0.1", "port": self._port, "log_level": "warning"},
                daemon=True,
            )
            self._server_thread.start()

    def stop(self) -> None:
        """Mark the agent as stopped. The daemon thread exits with the process."""
        with self._lock:
            self._running = False
            self._server_thread = None

    def metrics(self) -> dict:
        """Get a snapshot of current system metrics."""
        from bannin.core.gpu import get_gpu_metrics
        data = get_all_metrics()
        data["gpu"] = get_gpu_metrics()
        return data


def progress(name: str, current: int, total: int | None = None, *, port: int = 8420) -> None:
    """Report training progress to the running Bannin agent.

    Call this from any script to push progress to the dashboard without
    needing bannin.watch(). The CLI agent must be running separately.
    Silently ignores network failures (agent not running, connection refused).
    Raises ValueError for obviously invalid inputs.

    The HTTP POST has a 2-second timeout. For tight training loops, consider
    calling every N iterations rather than every single step.

    Usage:
        import bannin
        for epoch in range(1, 11):
            train_epoch()
            bannin.progress("Training GPT", current=epoch, total=10)
    """
    if not name or not isinstance(name, str):
        raise ValueError("name must be a non-empty string")
    if not isinstance(current, int) or current < 0:
        raise ValueError("current must be a non-negative integer")
    if total is not None and (not isinstance(total, int) or total < 1):
        raise ValueError("total must be a positive integer or None")

    import json
    import os
    import urllib.request

    payload = json.dumps({
        "name": name,
        "current": current,
        "total": total,
        "pid": os.getpid(),
    }).encode()

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/tasks",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        # Fire-and-forget: agent may not be running. No logging here because
        # this function is called from user scripts that may not have bannin
        # logging configured. The agent-side POST /tasks endpoint logs errors.
        pass


class watch:
    """Context manager that runs the Bannin agent during a block of code.

    Usage:
        with bannin.watch():
            train_model()
    """

    def __init__(self, port: int = 8420) -> None:
        self._agent = Bannin(port=port)

    def __enter__(self) -> Bannin:
        self._agent.start()
        self._history = None
        self._progress = None
        try:
            from bannin.intelligence.history import MetricHistory
            self._history = MetricHistory.get()
            self._history.start()
            from bannin.intelligence.progress import ProgressTracker
            self._progress = ProgressTracker.get()
            self._progress.hook_all()
        except Exception:
            if self._progress is not None:
                self._progress.unhook_all()
            if self._history is not None:
                self._history.stop()
            self._agent.stop()
            raise
        return self._agent

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> bool:
        if self._progress is not None:
            self._progress.unhook_all()
        if self._history is not None:
            self._history.stop()
        self._agent.stop()
        return False
