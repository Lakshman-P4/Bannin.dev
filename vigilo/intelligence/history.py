"""Metric history ring buffer — gives Vigilo a memory.

Stores timestamped metric snapshots in a fixed-size deque so that
downstream systems (OOM predictor, alerts, graphs) can look at trends
over the last N minutes instead of just a single snapshot.
"""

import collections
import threading
import time
from datetime import datetime, timezone

from vigilo.core.collector import get_memory_metrics, get_disk_metrics, get_cpu_metrics
from vigilo.core.gpu import get_gpu_metrics


class MetricHistory:
    """Singleton ring buffer that collects metrics on a background thread."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, max_readings: int = 360, interval_seconds: int = 5):
        self._max_readings = max_readings
        self._interval = interval_seconds
        self._readings = collections.deque(maxlen=max_readings)
        self._data_lock = threading.Lock()
        self._thread = None
        self._running = False

    @classmethod
    def get(cls) -> "MetricHistory":
        """Get or create the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls._create_from_config()
            return cls._instance

    @classmethod
    def _create_from_config(cls) -> "MetricHistory":
        """Create instance with settings from defaults.json."""
        try:
            from vigilo.config.loader import get_config
            cfg = get_config().get("intelligence", {})
            max_readings = cfg.get("history_max_readings", 360)
            interval = cfg.get("collection_interval_seconds", 5)
        except Exception:
            max_readings = 360
            interval = 5
        return cls(max_readings=max_readings, interval_seconds=interval)

    @classmethod
    def reset(cls):
        """Stop collection and reset the singleton. Mainly for testing."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop()
            cls._instance = None

    def start(self):
        """Start the background collection thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background collection thread."""
        self._running = False

    def _collection_loop(self):
        """Background loop that collects a snapshot every N seconds."""
        while self._running:
            try:
                snapshot = self._take_snapshot()
                with self._data_lock:
                    self._readings.append(snapshot)
            except Exception:
                pass

            # Also run alert evaluation on each cycle
            try:
                from vigilo.intelligence.alerts import ThresholdEngine
                ThresholdEngine.get().evaluate()
            except Exception:
                pass

            time.sleep(self._interval)

    def _take_snapshot(self) -> dict:
        """Collect a single timestamped snapshot of key metrics."""
        mem = get_memory_metrics()
        disk = get_disk_metrics()
        cpu = get_cpu_metrics()
        gpus = get_gpu_metrics()

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epoch": time.time(),
            "cpu_percent": cpu["percent"],
            "ram_percent": mem["percent"],
            "ram_used_gb": mem["used_gb"],
            "ram_available_gb": mem["available_gb"],
            "ram_total_gb": mem["total_gb"],
            "disk_percent": disk["percent"],
            "disk_used_gb": disk["used_gb"],
            "disk_free_gb": disk["free_gb"],
        }

        # Add GPU data if available
        if gpus:
            snapshot["gpu"] = []
            for g in gpus:
                snapshot["gpu"].append({
                    "index": g["index"],
                    "name": g["name"],
                    "memory_percent": g["memory_percent"],
                    "memory_used_mb": g["memory_used_mb"],
                    "memory_total_mb": g["memory_total_mb"],
                    "utilization_percent": g["gpu_utilization_percent"],
                    "temperature_c": g.get("temperature_c"),
                })

        return snapshot

    def get_memory_history(self, last_n_minutes: float = 5) -> list[dict]:
        """Get memory readings from the last N minutes.

        Returns a list of dicts with timestamp, ram_percent, ram_used_gb,
        and gpu data if available.
        """
        cutoff = time.time() - (last_n_minutes * 60)
        with self._data_lock:
            readings = list(self._readings)

        result = []
        for r in readings:
            if r["epoch"] >= cutoff:
                entry = {
                    "timestamp": r["timestamp"],
                    "ram_percent": r["ram_percent"],
                    "ram_used_gb": r["ram_used_gb"],
                    "ram_available_gb": r["ram_available_gb"],
                }
                if "gpu" in r:
                    entry["gpu"] = [
                        {"index": g["index"], "memory_percent": g["memory_percent"], "memory_used_mb": g["memory_used_mb"]}
                        for g in r["gpu"]
                    ]
                result.append(entry)
        return result

    def get_full_history(self, last_n_minutes: float = 5) -> list[dict]:
        """Get full snapshots (CPU, RAM, disk, GPU) from the last N minutes."""
        cutoff = time.time() - (last_n_minutes * 60)
        with self._data_lock:
            readings = list(self._readings)
        return [r for r in readings if r["epoch"] >= cutoff]

    def get_latest(self) -> dict | None:
        """Get the most recent snapshot, or None if no data yet."""
        with self._data_lock:
            return self._readings[-1] if self._readings else None

    @property
    def reading_count(self) -> int:
        """How many readings are currently stored."""
        with self._data_lock:
            return len(self._readings)
