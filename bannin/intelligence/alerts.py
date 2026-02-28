"""Threshold engine — evaluates alert rules against current metrics.

Reads configurable rules from defaults.json and checks them against
live system data every collection cycle. Handles deduplication
(cooldowns) so the same alert doesn't fire repeatedly.
"""

from __future__ import annotations

import collections
import operator as op
import threading
import time
from datetime import datetime, timezone
from typing import Any

from bannin.log import logger


# Map string operators to Python functions
_OPERATORS = {
    ">=": op.ge,
    "<=": op.le,
    ">": op.gt,
    "<": op.lt,
    "==": op.eq,
    "!=": op.ne,
}


class ThresholdEngine:
    """Singleton that evaluates alert rules and tracks alert history."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._rules = self._load_rules()
        self._alert_history: collections.deque = collections.deque(maxlen=2000)
        self._last_fired: dict[str, float] = {}
        self._data_lock = threading.RLock()
        self._current_platform = self._detect_platform()

    @classmethod
    def get(cls) -> "ThresholdEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def _load_rules(self) -> list[dict]:
        try:
            from bannin.config.loader import get_config
            cfg = get_config().get("intelligence", {}).get("alerts", {})
            return cfg.get("rules", [])
        except Exception:
            logger.debug("Config unavailable for alert rules, using empty ruleset")
            return []

    def _detect_platform(self) -> str:
        try:
            from bannin.platforms.detector import detect_platform
            return detect_platform()
        except Exception:
            logger.debug("Platform detection failed, defaulting to 'local'")
            return "local"

    def evaluate(self, metrics_snapshot: dict | None = None) -> list[dict]:
        """Evaluate all rules against current metrics. Returns newly fired alerts."""
        if metrics_snapshot is None:
            metrics_snapshot = self._collect_metrics()

        now = time.time()
        new_alerts = []

        for rule in self._rules:
            # Check platform filter
            platforms = rule.get("platforms", ["all"])
            if "all" not in platforms and self._current_platform not in platforms:
                continue

            # Check cooldown
            rule_id = rule["id"]
            cooldown = rule.get("cooldown_seconds", 60)
            with self._data_lock:
                last = self._last_fired.get(rule_id, 0)
            if now - last < cooldown:
                continue

            # Resolve the metric value from the snapshot
            metric_path = rule.get("metric", "")
            value = self._resolve_metric(metric_path, metrics_snapshot)
            if value is None:
                continue

            # Check the condition
            threshold = rule.get("threshold")
            compare_to = rule.get("compare_to")
            operator_str = rule.get("operator", ">=")
            op_func = _OPERATORS.get(operator_str)
            if not op_func:
                continue

            # If compare_to is set, compare value to another metric instead of threshold
            if compare_to:
                compare_value = self._resolve_metric(compare_to, metrics_snapshot)
                if compare_value is None:
                    continue
                triggered = op_func(value, compare_value)
            else:
                if threshold is None:
                    continue
                triggered = op_func(value, threshold)

            # Check additional condition if present
            condition = rule.get("condition")
            if triggered and condition:
                triggered = self._evaluate_condition(condition, metrics_snapshot)

            if triggered:
                # Format the message
                message = rule.get("message", f"Alert: {rule_id}")
                message = message.replace("{value}", str(round(value, 1) if isinstance(value, float) else value))
                message = message.replace("{value_human}", _format_seconds(value) if isinstance(value, (int, float)) else str(value))

                alert = {
                    "id": rule_id,
                    "severity": rule.get("severity", "info"),
                    "message": message,
                    "value": round(value, 2) if isinstance(value, float) else value,
                    "threshold": threshold,
                    "fired_at": datetime.now(timezone.utc).isoformat(),
                    "fired_epoch": now,
                }

                with self._data_lock:
                    self._alert_history.append(alert)
                    self._last_fired[rule_id] = now
                    # Bound _last_fired to prevent unbounded growth
                    # Evict oldest entries to preserve recent cooldown state
                    if len(self._last_fired) > 500:
                        oldest_keys = sorted(
                            self._last_fired, key=lambda k: self._last_fired.get(k, 0.0),
                        )[:100]
                        for k in oldest_keys:
                            del self._last_fired[k]
                new_alerts.append(alert)

                # Emit to analytics pipeline
                try:
                    from bannin.analytics.pipeline import EventPipeline
                    EventPipeline.get().emit({
                        "type": "alert",
                        "source": "alerts",
                        "severity": alert.get("severity", "info"),
                        "message": alert.get("message", ""),
                        "data": {"rule_id": rule_id, "value": alert.get("value"), "threshold": threshold},
                    })
                except Exception:
                    logger.debug("Failed to emit alert event to pipeline")

        return new_alerts

    def _resolve_metric(self, path: str, snapshot: dict) -> Any | None:
        """Resolve a dot-path like 'memory.percent' from the metrics snapshot."""
        parts = path.split(".")
        current = snapshot
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _evaluate_condition(self, condition: str, snapshot: dict) -> bool:
        """Evaluate a simple condition like 'predictions.oom.ram.confidence >= 70'."""
        # Parse: "metric.path operator value"
        parts = condition.strip().split()
        if len(parts) != 3:
            logger.warning("Cannot parse alert condition (expected 3 parts): %s", condition)
            return False

        metric_path, operator_str, threshold_str = parts
        value = self._resolve_metric(metric_path, snapshot)
        if value is None:
            return False

        try:
            threshold = float(threshold_str)
        except ValueError:
            logger.warning("Cannot parse threshold as float in condition: %s", condition)
            return False

        op_func = _OPERATORS.get(operator_str)
        if not op_func:
            logger.warning("Unknown operator '%s' in condition: %s", operator_str, condition)
            return False

        return op_func(value, threshold)

    def _collect_metrics(self) -> dict:
        """Gather all current metrics into a flat-ish dict for rule evaluation."""
        snapshot = {}

        # System metrics
        try:
            from bannin.core.collector import get_memory_metrics, get_disk_metrics, get_cpu_metrics
            snapshot["memory"] = get_memory_metrics()
            snapshot["disk"] = get_disk_metrics()
            snapshot["cpu"] = get_cpu_metrics()
        except Exception:
            logger.debug("Failed to collect system metrics for alert evaluation")

        # GPU metrics
        try:
            from bannin.core.gpu import get_gpu_metrics
            gpus = get_gpu_metrics()
            if gpus:
                # Use the first GPU for simple threshold checks
                snapshot["gpu"] = gpus[0]
                snapshot["gpus"] = gpus
        except Exception:
            logger.debug("Failed to collect GPU metrics for alert evaluation")

        # OOM predictions (reuse a cached instance to avoid re-loading config each cycle)
        try:
            from bannin.intelligence.oom import OOMPredictor
            predictor = OOMPredictor.get()
            snapshot["predictions"] = {"oom": predictor.predict()}
        except Exception:
            logger.debug("Failed to get OOM predictions for alert evaluation")

        # Task tracking
        try:
            from bannin.intelligence.progress import ProgressTracker
            tasks_data = ProgressTracker.get().get_tasks()
            active = tasks_data.get("active_tasks", [])
            completed = tasks_data.get("completed_tasks", [])

            # Derived metrics for alert rules
            all_done = len(active) == 0 and len(completed) > 0
            longest_eta = max((t.get("eta_seconds") or 0 for t in active), default=0)

            snapshot["tasks"] = {
                "active_count": len(active),
                "completed_count": len(completed),
                "all_completed": all_done,
                "longest_eta_seconds": longest_eta,
            }
        except Exception:
            logger.debug("Failed to collect task data for alert evaluation")

        # LLM metrics + health score
        try:
            from bannin.llm.tracker import LLMTracker
            tracker = LLMTracker.get()
            summary = tracker.get_summary()
            snapshot["llm"] = {
                "total_cost_usd": summary.get("total_cost_usd", 0),
                "total_calls": summary.get("total_calls", 0),
            }

            # Wire health score into snapshot for alert rules
            try:
                session_fatigue = None
                vram_pressure = None
                try:
                    from bannin.state import get_mcp_session_data
                    mcp_data = get_mcp_session_data()
                    if mcp_data:
                        session_fatigue = mcp_data
                except Exception:
                    logger.debug("MCP session data unavailable for alert health check")
                try:
                    from bannin.llm.ollama import OllamaMonitor
                    ollama = OllamaMonitor.get().get_health()
                    if ollama.get("available"):
                        vram_pressure = ollama.get("vram_pressure")
                except Exception:
                    logger.debug("Ollama health unavailable for alert health check")

                health = tracker.get_health(
                    session_fatigue=session_fatigue,
                    vram_pressure=vram_pressure,
                )
                snapshot["llm"]["health_score"] = health.get("health_score", 100)
                snapshot["llm"]["health_rating"] = health.get("rating", "excellent")
            except Exception:
                logger.debug("Failed to compute LLM health for alert evaluation")
        except Exception:
            logger.debug("Failed to collect LLM metrics for alert evaluation")

        # Ollama metrics
        try:
            from bannin.llm.ollama import OllamaMonitor
            ollama_health = OllamaMonitor.get().get_health()
            if ollama_health.get("available"):
                snapshot["ollama"] = {
                    "vram_pressure": ollama_health.get("vram_pressure", 0),
                    "model_count": ollama_health.get("model_count", 0),
                }
        except Exception:
            logger.debug("Failed to collect Ollama metrics for alert evaluation")

        # MCP session metrics (from pushed data)
        try:
            from bannin.state import get_mcp_session_data
            mcp_data = get_mcp_session_data()
            if mcp_data:
                snapshot["mcp"] = {
                    "session_fatigue": mcp_data.get("session_fatigue", 0),
                    "total_tool_calls": mcp_data.get("total_tool_calls", 0),
                    "session_duration_minutes": mcp_data.get("session_duration_minutes", 0),
                }
        except Exception:
            logger.debug("Failed to collect MCP session metrics for alert evaluation")

        # Platform metrics
        try:
            from bannin.platforms.detector import detect_platform
            plat = detect_platform()
            if plat == "colab":
                from bannin.platforms.colab import get_colab_metrics
                platform_data = get_colab_metrics()
                session = platform_data.get("session", {})
                snapshot["platform"] = {
                    "session": {"remaining_seconds": session.get("remaining_seconds", 99999)},
                    "storage": {"percent": platform_data.get("storage", {}).get("percent_used", 0)},
                }
            elif plat == "kaggle":
                from bannin.platforms.kaggle import get_kaggle_metrics
                platform_data = get_kaggle_metrics()
                session = platform_data.get("session", {})
                snapshot["platform"] = {
                    "session": {"remaining_seconds": session.get("remaining_seconds", 99999)},
                    "storage": {"percent": platform_data.get("storage", {}).get("percent_used", 0)},
                    "gpu_quota": {"remaining_hours": platform_data.get("quotas", {}).get("gpu_remaining_hours", 99)},
                }
        except Exception:
            logger.debug("Failed to collect platform metrics for alert evaluation")

        return snapshot

    def get_alerts(self, limit: int | None = None) -> dict:
        """Get full alert history for this session."""
        with self._data_lock:
            alerts = [dict(a) for a in reversed(self._alert_history)]
            total_fired = len(self._alert_history)
        if limit:
            alerts = alerts[:limit]
        return {
            "total_fired": total_fired,
            "alerts": alerts,
        }

    def get_active_alerts(self) -> dict:
        """Get currently active alerts — only if the condition is STILL true.

        Copies _last_fired and _alert_history under lock, then releases the
        lock before expensive metric resolution to avoid blocking writers.
        """
        now = time.time()
        active = []

        # Build rule lookups
        rules_by_id = {r["id"]: r for r in self._rules}

        # Snapshot shared state under lock, then release before I/O
        with self._data_lock:
            fired_snapshot = dict(self._last_fired)
            history_snapshot = list(self._alert_history)

        # Collect current metrics (expensive — no lock held)
        current = self._collect_metrics()

        for rule_id, last_epoch in fired_snapshot.items():
            rule = rules_by_id.get(rule_id)
            if not rule:
                continue

            cooldown = rule.get("cooldown_seconds", 60)
            if now - last_epoch >= cooldown:
                continue

            # Re-check: is the condition STILL true right now?
            metric_path = rule.get("metric", "")
            value = self._resolve_metric(metric_path, current)
            if value is None:
                continue

            threshold = rule.get("threshold")
            compare_to = rule.get("compare_to")
            operator_str = rule.get("operator", ">=")
            op_func = _OPERATORS.get(operator_str)
            if not op_func:
                continue

            # Re-evaluate: compare_to rules compare two metrics;
            # threshold rules compare metric to a fixed value
            if compare_to:
                compare_value = self._resolve_metric(compare_to, current)
                if compare_value is None or not op_func(value, compare_value):
                    continue
            elif threshold is not None:
                if not op_func(value, threshold):
                    continue  # Condition no longer true — suppress alert
            else:
                continue  # Neither threshold nor compare_to — skip

            # Find the most recent alert for this rule from snapshot
            for alert in reversed(history_snapshot):
                if alert["id"] == rule_id:
                    active.append(dict(alert))
                    break

        return {
            "active": active,
            "count": len(active),
        }


def _format_seconds(seconds: float | int | str) -> str:
    """Format seconds into human-readable time."""
    try:
        seconds = int(float(seconds))
    except (ValueError, TypeError):
        return str(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m {seconds % 60}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60}m"
