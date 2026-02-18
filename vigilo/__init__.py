__version__ = "0.1.0"

from vigilo.core.collector import get_all_metrics
from vigilo.llm.wrapper import wrap
from vigilo.llm.tracker import track


class Vigilo:
    """Main Vigilo agent — collects metrics and exposes API."""

    def __init__(self, port: int = 8420):
        self._port = port
        self._server_thread = None

    def start(self):
        """Start the agent API server in a background thread."""
        import threading
        import uvicorn
        from vigilo.api import app

        self._server_thread = threading.Thread(
            target=uvicorn.run,
            kwargs={"app": app, "host": "127.0.0.1", "port": self._port, "log_level": "warning"},
            daemon=True,
        )
        self._server_thread.start()

    def metrics(self) -> dict:
        """Get a snapshot of current system metrics."""
        from vigilo.core.gpu import get_gpu_metrics
        data = get_all_metrics()
        data["gpu"] = get_gpu_metrics()
        return data


class watch:
    """Context manager that runs the Vigilo agent during a block of code.

    Usage:
        with vigilo.watch():
            train_model()
    """

    def __init__(self, port: int = 8420):
        self._agent = Vigilo(port=port)

    def __enter__(self):
        self._agent.start()
        return self._agent

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
