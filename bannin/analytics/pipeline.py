"""Async event pipeline -- non-blocking event ingestion with batched writes.

All Bannin components emit events through this pipeline. Events are
buffered in a bounded queue and flushed to the analytics store in
batches. The agent never blocks for analytics -- if the queue is full,
oldest events are dropped.
"""

from __future__ import annotations

import platform
import queue
import threading
import time

from bannin.log import logger


class EventPipeline:
    """Singleton non-blocking event pipeline with background consumer."""

    _instance: EventPipeline | None = None
    _lock = threading.Lock()

    def __init__(self, max_queue_size: int = 10000, flush_interval: float = 2.0, flush_batch: int = 100) -> None:
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._flush_interval = flush_interval
        self._flush_batch = flush_batch
        self._running = False
        self._lifecycle_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._machine = platform.node()
        self._downsample_lock = threading.Lock()
        self._downsample_last: dict[str, float] = {}
        self._dropped_lock = threading.Lock()
        self._dropped_count: int = 0

    @classmethod
    def get(cls) -> "EventPipeline":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop()
            cls._instance = None

    def start(self) -> None:
        """Start the background consumer thread."""
        with self._lifecycle_lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._consumer_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the consumer thread, flushing remaining events."""
        with self._lifecycle_lock:
            if not self._running:
                return
            self._running = False
            thread = self._thread
            self._thread = None
        if thread and thread.is_alive():
            thread.join(timeout=5)
        self._flush()

    @property
    def dropped_count(self) -> int:
        """Number of events dropped due to queue overflow."""
        with self._dropped_lock:
            return self._dropped_count

    def emit(self, event: dict) -> None:
        """Non-blocking event emission. Drops oldest on overflow.

        Event schema:
            ts: float (auto-set)
            source: str (e.g., "system", "llm", "mcp", "ollama", "alerts")
            machine: str (auto-set)
            type: str (e.g., "alert", "metric_snapshot", "llm_call", ...)
            severity: str | None
            data: dict
            message: str
        """
        # Apply downsampling for metric_snapshot (one per 5 minutes for long-term)
        event_type = event.get("type", "")
        if event_type == "metric_snapshot":
            now = time.time()
            with self._downsample_lock:
                last = self._downsample_last.get("metric_snapshot", 0)
                if now - last < 300:  # 5 minutes
                    return
                self._downsample_last["metric_snapshot"] = now

        # Enrich event
        enriched = {
            "ts": time.time(),
            "source": event.get("source", "unknown"),
            "machine": self._machine,
            "type": event_type,
            "severity": event.get("severity"),
            "data": event.get("data", {}),
            "message": event.get("message", ""),
        }

        try:
            self._queue.put_nowait(enriched)
        except queue.Full:
            # Drop oldest to make room
            try:
                self._queue.get_nowait()
                with self._dropped_lock:
                    self._dropped_count += 1
                self._queue.put_nowait(enriched)
            except (queue.Empty, queue.Full):
                with self._dropped_lock:
                    self._dropped_count += 1

    def _consumer_loop(self) -> None:
        """Background loop: drain queue in batches and write to store."""
        try:
            while True:
                with self._lifecycle_lock:
                    if not self._running:
                        break
                try:
                    time.sleep(self._flush_interval)
                    self._flush()
                except Exception:
                    logger.warning("EventPipeline consumer loop error", exc_info=True)
        finally:
            # Ensure _running is reset even on BaseException (KeyboardInterrupt, etc.)
            with self._lifecycle_lock:
                self._running = False

    def _flush(self) -> None:
        """Drain up to flush_batch events and write to store."""
        batch = []
        for _ in range(self._flush_batch):
            try:
                event = self._queue.get_nowait()
                batch.append(event)
            except queue.Empty:
                break

        if not batch:
            return

        try:
            from bannin.analytics.store import AnalyticsStore
            store = AnalyticsStore.get()
            store.write_events(batch)
        except Exception:
            logger.warning("EventPipeline failed to write %d events to store", len(batch), exc_info=True)
