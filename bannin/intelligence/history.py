"""Metric history ring buffer — gives Bannin a memory.

Stores timestamped metric snapshots in a fixed-size deque so that
downstream systems (OOM predictor, alerts, graphs) can look at trends
over the last N minutes instead of just a single snapshot.
"""

from __future__ import annotations

import collections
import threading
import time
from datetime import datetime, timezone

from bannin.core.collector import get_memory_metrics, get_disk_metrics, get_cpu_metrics
from bannin.core.gpu import get_gpu_metrics
from bannin.log import logger


class MetricHistory:
    """Singleton ring buffer that collects metrics on a background thread."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self, max_readings: int = 900, interval_seconds: int = 2) -> None:
        self._max_readings = max_readings
        self._interval = interval_seconds
        self._readings = collections.deque(maxlen=max_readings)
        self._data_lock = threading.Lock()
        self._thread = None
        self._running = False
        self._stop_event = threading.Event()
        self._cycle_count = 0
        self._cached_disk: dict | None = None
        self._cached_gpu: list | None = None

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
            from bannin.config.loader import get_config
            cfg = get_config().get("intelligence", {})
            max_readings = cfg.get("history_max_readings", 900)
            interval = cfg.get("collection_interval_seconds", 2)
        except Exception:
            logger.debug("Config unavailable for MetricHistory, using defaults")
            max_readings = 900
            interval = 2
        return cls(max_readings=max_readings, interval_seconds=interval)

    @classmethod
    def reset(cls) -> None:
        """Stop collection and reset the singleton. Mainly for testing."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop()
            cls._instance = None

    def start(self) -> None:
        """Start the background collection thread."""
        with self._data_lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background collection thread."""
        with self._data_lock:
            self._running = False
        self._stop_event.set()

    def _is_running(self) -> bool:
        """Check running flag under lock."""
        with self._data_lock:
            return self._running

    def _collection_loop(self) -> None:
        """Background loop that collects a snapshot every N seconds.

        Subtracts elapsed collection time from the sleep interval to prevent
        drift (interval = target, not target + collection_time).
        """
        while not self._stop_event.is_set():
            cycle_start = time.monotonic()
            snapshot = None
            try:
                snapshot = self._take_snapshot()
                with self._data_lock:
                    self._readings.append(snapshot)

                # Emit to analytics pipeline (downsampled inside pipeline)
                try:
                    from bannin.analytics.pipeline import EventPipeline
                    EventPipeline.get().emit({
                        "type": "metric_snapshot",
                        "source": "system",
                        "severity": None,
                        "message": f"CPU {snapshot['cpu_percent']:.0f}%, RAM {snapshot['ram_percent']:.0f}%, Disk {snapshot['disk_percent']:.0f}%",
                        "data": {
                            "cpu_percent": snapshot["cpu_percent"],
                            "ram_percent": snapshot["ram_percent"],
                            "ram_used_gb": snapshot["ram_used_gb"],
                            "disk_percent": snapshot["disk_percent"],
                        },
                    })
                except Exception:
                    logger.debug("Failed to emit metric snapshot to pipeline")
            except Exception:
                logger.warning("MetricHistory collection loop error", exc_info=True)

            # Run alert evaluation every other cycle, passing the snapshot
            # we already collected (avoids duplicate psutil calls)
            with self._data_lock:
                run_alerts = snapshot is not None and self._cycle_count % 2 == 0
                self._cycle_count += 1

            if run_alerts:
                try:
                    from bannin.intelligence.alerts import ThresholdEngine
                    ThresholdEngine.get().evaluate(metrics_snapshot={
                        "memory": {"percent": snapshot["ram_percent"],
                                   "used_gb": snapshot["ram_used_gb"],
                                   "available_gb": snapshot["ram_available_gb"],
                                   "total_gb": snapshot["ram_total_gb"]},
                        "disk": {"percent": snapshot["disk_percent"],
                                 "used_gb": snapshot["disk_used_gb"],
                                 "free_gb": snapshot["disk_free_gb"]},
                        "cpu": {"percent": snapshot["cpu_percent"]},
                        "gpu": snapshot.get("gpu", []),
                    })
                except Exception:
                    logger.debug("Alert evaluation failed in collection loop", exc_info=True)

            elapsed = time.monotonic() - cycle_start
            self._stop_event.wait(timeout=max(0, self._interval - elapsed))

    def _take_snapshot(self) -> dict:
        """Collect a single timestamped snapshot of key metrics.

        CPU and RAM are collected every cycle (they change fast).
        Disk and GPU are collected every 8th cycle (~32s) and cached
        since they change slowly -- saves significant CPU.
        """
        mem = get_memory_metrics()
        cpu = get_cpu_metrics()

        # Read cycle count and cache under lock to avoid races
        with self._data_lock:
            cycle = self._cycle_count
            cached_disk = self._cached_disk
            cached_gpu = self._cached_gpu

        # Disk and GPU: refresh every 8 cycles, use cache otherwise
        if cycle % 8 == 0 or cached_disk is None:
            cached_disk = get_disk_metrics()
            cached_gpu = get_gpu_metrics()
            with self._data_lock:
                self._cached_disk = cached_disk
                self._cached_gpu = cached_gpu
        disk = cached_disk
        gpus = cached_gpu

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
        """Get the most recent snapshot, or None if no data yet.

        Returns a shallow copy to prevent callers from mutating internal state.
        """
        with self._data_lock:
            return dict(self._readings[-1]) if self._readings else None

    @property
    def reading_count(self) -> int:
        """How many readings are currently stored."""
        with self._data_lock:
            return len(self._readings)
