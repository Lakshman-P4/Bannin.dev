__version__ = "0.1.0"

from bannin.core.collector import get_all_metrics
from bannin.llm.wrapper import wrap
from bannin.llm.tracker import track


class Bannin:
    """Main Bannin agent — collects metrics and exposes API."""

    def __init__(self, port: int = 8420):
        self._port = port
        self._server_thread = None

    def start(self):
        """Start the agent API server in a background thread."""
        import threading
        import uvicorn
        from bannin.api import app

        self._server_thread = threading.Thread(
            target=uvicorn.run,
            kwargs={"app": app, "host": "127.0.0.1", "port": self._port, "log_level": "warning"},
            daemon=True,
        )
        self._server_thread.start()

    def metrics(self) -> dict:
        """Get a snapshot of current system metrics."""
        from bannin.core.gpu import get_gpu_metrics
        data = get_all_metrics()
        data["gpu"] = get_gpu_metrics()
        return data


class watch:
    """Context manager that runs the Bannin agent during a block of code.

    Usage:
        with bannin.watch():
            train_model()
    """

    def __init__(self, port: int = 8420):
        self._agent = Bannin(port=port)

    def __enter__(self):
        self._agent.start()
        # Start background metric history collection
        from bannin.intelligence.history import MetricHistory
        self._history = MetricHistory.get()
        self._history.start()
        # Start progress detection (tqdm + stdout interception)
        from bannin.intelligence.progress import ProgressTracker
        self._progress = ProgressTracker.get()
        self._progress.hook_all()
        return self._agent

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._progress.unhook_all()
        self._history.stop()
        return False
