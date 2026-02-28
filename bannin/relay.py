"""WebSocket relay client -- pushes agent data to the Bannin relay server.

Connects to the relay server's /ws/agent endpoint, authenticates with an
API key, and periodically pushes system metrics, alerts, OOM predictions,
training status, processes, and health data. Handles reconnection with
exponential backoff and responds to training stop/kill commands from the
relay.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

from bannin.log import logger


_MAX_RECONNECT_DELAY = 60.0
_BASE_RECONNECT_DELAY = 2.0
_METRICS_INTERVAL = 5.0
_HEARTBEAT_INTERVAL = 25.0


class RelayClient:
    """Async WebSocket client that pushes agent data to the relay server."""

    def __init__(self, relay_url: str, api_key: str) -> None:
        self._relay_url = relay_url.rstrip("/")
        self._api_key = api_key
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._start_time = time.monotonic()
        self._last_alert_count = 0  # Track how many alerts we've already sent

    async def start(self) -> None:
        """Start the relay client background task. Idempotent."""
        if self._running:
            return
        self._running = True
        self._start_time = time.monotonic()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Relay client started, target: %s", self._relay_url)

    async def stop(self) -> None:
        """Stop the relay client and close the WebSocket connection."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Relay client stopped")

    async def _run_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        attempt = 0
        while self._running:
            try:
                await self._connect()
                # If _connect returns normally (clean close), reset backoff
                attempt = 0
            except asyncio.CancelledError:
                break
            except Exception as exc:
                attempt += 1
                delay = min(
                    _BASE_RECONNECT_DELAY * (2 ** min(attempt, 8)),
                    _MAX_RECONNECT_DELAY,
                )
                logger.warning(
                    "Relay connection failed (attempt %d): %s -- retrying in %.1fs",
                    attempt, exc, delay,
                )
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    break

    async def _connect(self) -> None:
        """Establish WebSocket connection and run push loops."""
        import websockets

        ws_url = self._relay_url.replace("http://", "ws://").replace("https://", "wss://")
        url = f"{ws_url}/ws/agent?key={self._api_key}"

        async with websockets.connect(
            url,
            ping_interval=None,  # Relay server handles ping/pong
            close_timeout=5,
            max_size=2 * 1024 * 1024,
        ) as ws:
            logger.info("Connected to relay server")

            # Run data pushers and message listener concurrently
            metrics_task = asyncio.create_task(self._push_loop(ws))
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(ws))
            listener_task = asyncio.create_task(self._listen(ws))

            done, pending = await asyncio.wait(
                [metrics_task, heartbeat_task, listener_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Re-raise any exception from the completed task
            for task in done:
                exc = task.exception()
                if exc is not None:
                    raise exc

    async def _push_loop(self, ws: Any) -> None:
        """Periodically collect and push all data types."""
        while self._running:
            try:
                await self._push_all(ws)
            except Exception:
                # Connection error -- let reconnect handle it
                raise
            await asyncio.sleep(_METRICS_INTERVAL)

    async def _heartbeat_loop(self, ws: Any) -> None:
        """Send heartbeat messages to keep the connection alive."""
        while self._running:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            try:
                uptime = time.monotonic() - self._start_time
                await self._send(ws, "heartbeat", {
                    "uptime_seconds": round(uptime, 1),
                })
            except Exception:
                raise

    async def _listen(self, ws: Any) -> None:
        """Listen for incoming messages from the relay (training stop, etc).

        Message handling runs in a thread pool to avoid blocking the event loop
        (kill_process can block for up to 3 seconds waiting for graceful shutdown).
        """
        loop = asyncio.get_running_loop()
        async for raw in ws:
            if not self._running:
                break
            try:
                msg = json.loads(raw)
                await loop.run_in_executor(None, self._handle_relay_message, msg)
            except json.JSONDecodeError:
                logger.debug("Relay sent invalid JSON")

    async def _push_all(self, ws: Any) -> None:
        """Collect all data sources and push to relay."""
        loop = asyncio.get_running_loop()

        # Collect data in thread pool (all collectors are synchronous)
        metrics_data = await loop.run_in_executor(None, _collect_metrics)
        if metrics_data is not None:
            await self._send(ws, "metrics", metrics_data)

        processes_data = await loop.run_in_executor(None, _collect_processes)
        if processes_data is not None:
            await self._send(ws, "processes", processes_data)

        alerts_data, new_count = await loop.run_in_executor(
            None, _collect_new_alerts, self._last_alert_count,
        )
        if alerts_data:
            for alert in alerts_data:
                await self._send(ws, "alert", alert)
        self._last_alert_count = new_count

        oom_data = await loop.run_in_executor(None, _collect_oom)
        if oom_data is not None:
            await self._send(ws, "oom_prediction", oom_data)

        training_data = await loop.run_in_executor(None, _collect_training)
        if training_data is not None:
            await self._send(ws, "training", training_data)

        health_data = await loop.run_in_executor(None, _collect_health)
        if health_data is not None:
            await self._send(ws, "health", health_data)

    async def _send(self, ws: Any, msg_type: str, data: dict) -> None:
        """Send a typed message to the relay server."""
        payload = {
            "type": msg_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        await ws.send(json.dumps(payload, default=str))

    def _handle_relay_message(self, msg: dict) -> None:
        """Handle commands from the relay server."""
        msg_type = msg.get("type")
        if msg_type == "training_stop":
            task_id = msg.get("taskId", "")
            if task_id:
                logger.info("Received training stop request for task %s", task_id)
                self._stop_training_task(task_id, force=False)
        elif msg_type == "training_kill":
            task_id = msg.get("taskId", "")
            if task_id:
                logger.warning("Received training kill request for task %s", task_id)
                self._stop_training_task(task_id, force=True)
        else:
            logger.debug("Unknown relay message type: %s", msg_type)

    def _stop_training_task(self, task_id: str, *, force: bool) -> None:
        """Stop a training task by terminating or killing its process via PID.

        Supports two ID conventions:
        - ``"pid_<N>"`` -- detected training processes (from TrainingDetector).
          The PID is extracted directly; no ProgressTracker lookup needed.
        - Any other string -- tracked tasks (from ProgressTracker).  The PID is
          resolved via ``tracker.get_task_pid()``.

        Args:
            task_id: The task to stop.
            force: If True, send SIGKILL immediately. If False, use graceful
                   SIGTERM with a 3-second wait before escalating to SIGKILL.
        """
        import psutil

        is_detected = task_id.startswith("pid_")

        if is_detected:
            # Detected process -- PID is embedded in the ID
            try:
                pid = int(task_id[4:])
            except (ValueError, IndexError):
                logger.warning("Training stop: invalid pid-prefixed ID %r", task_id)
                return
        else:
            # Tracked task -- resolve PID via ProgressTracker
            from bannin.intelligence.progress import ProgressTracker

            pid = ProgressTracker.get().get_task_pid(task_id)
            if not pid:
                logger.warning("Training stop: task %s has no PID or not found", task_id)
                return

        if force:
            # Immediate SIGKILL -- no grace period
            try:
                proc = psutil.Process(pid)
                proc.kill()
                logger.info("Training killed: SIGKILL sent to PID %d for task %s", pid, task_id)
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                logger.warning("Training kill failed for task %s (PID %d): %s", task_id, pid, exc)
                return
        else:
            # Graceful stop via existing kill_process (SIGTERM -> 3s wait -> SIGKILL)
            from bannin.core.process import kill_process

            result = kill_process(pid)
            if result["status"] != "ok":
                logger.warning(
                    "Training stop failed for task %s (PID %d): %s",
                    task_id, pid, result["message"],
                )
                return
            logger.info("Training stopped: killed PID %d for task %s", pid, task_id)

        # Mark the task as completed/finished after successful termination
        if is_detected:
            from bannin.intelligence.training import TrainingDetector

            TrainingDetector.get().mark_finished(pid)
        else:
            from bannin.intelligence.progress import ProgressTracker

            tracker = ProgressTracker.get()
            task = tracker.get_task(task_id)
            current = task.get("current") if task else None
            tracker._complete_task(task_id, final_current=current)


# ---------------------------------------------------------------------------
# Data collectors -- synchronous functions called via run_in_executor
# ---------------------------------------------------------------------------

def _collect_metrics() -> dict | None:
    """Collect system metrics in the relay-expected shape."""
    try:
        from bannin.core.collector import get_all_metrics
        from bannin.core.gpu import get_gpu_metrics

        data = get_all_metrics()
        gpu = get_gpu_metrics()

        return {
            "cpu": data["cpu"],
            "memory": data["memory"],
            "disk": data["disk"],
            "network": data["network"],
            "gpu": gpu,
        }
    except Exception:
        logger.debug("Failed to collect metrics for relay", exc_info=True)
        return None


def _collect_processes() -> dict | None:
    """Collect process data in the relay-expected shape."""
    try:
        from bannin.core.process import (
            get_process_count, get_grouped_processes, get_resource_breakdown,
        )

        return {
            "summary": get_process_count(),
            "top_processes": get_grouped_processes(limit=15),
            "resource_breakdown": get_resource_breakdown(),
        }
    except Exception:
        logger.debug("Failed to collect processes for relay", exc_info=True)
        return None


def _collect_new_alerts(last_count: int) -> tuple[list[dict], int]:
    """Collect only NEW alerts since the last push.

    Uses the full alert history and compares count to detect new entries.
    Returns (new_alerts, current_total_count).
    """
    try:
        from bannin.intelligence.alerts import ThresholdEngine

        result = ThresholdEngine.get().get_alerts()
        all_alerts: list[dict] = result.get("alerts", [])
        total: int = result.get("total_fired", len(all_alerts))

        if total <= last_count:
            return [], total

        # Alerts are returned newest-first; we need the (total - last_count) newest
        new_count = total - last_count
        new_alerts = all_alerts[:new_count]
        return new_alerts, total
    except Exception:
        logger.debug("Failed to collect alerts for relay", exc_info=True)
        return [], last_count


def _collect_oom() -> dict | None:
    """Collect OOM prediction data."""
    try:
        from bannin.intelligence.oom import OOMPredictor

        return OOMPredictor.get().predict()
    except Exception:
        logger.debug("Failed to collect OOM prediction for relay", exc_info=True)
        return None


def _collect_training() -> dict | None:
    """Collect training progress data."""
    try:
        from bannin.intelligence.progress import ProgressTracker

        return ProgressTracker.get().get_tasks()
    except Exception:
        logger.debug("Failed to collect training status for relay", exc_info=True)
        return None


def _collect_health() -> dict | None:
    """Collect LLM health data."""
    try:
        from bannin.llm.aggregator import compute_health

        return compute_health()
    except Exception:
        logger.debug("Failed to collect health for relay", exc_info=True)
        return None
