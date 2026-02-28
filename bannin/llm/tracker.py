"""LLM usage tracker -- stores all API call data and provides summaries.

The tracker is a singleton that accumulates usage across the entire session.
Calls are stored in a bounded deque to prevent unbounded memory growth
in long-running sessions.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from types import TracebackType

from bannin.log import logger
from bannin.llm.pricing import calculate_cost, get_context_window, get_provider

_MAX_CALLS = 5000  # Retain last 5000 API calls (~72h at 1 call/min)


class LLMTracker:
    """Central store for all LLM API call data."""

    _instance: LLMTracker | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._calls: deque[dict] = deque(maxlen=_MAX_CALLS)
        self._data_lock = threading.Lock()
        self._session_start = time.time()

    @classmethod
    def get(cls) -> "LLMTracker":
        """Get the global tracker instance (creates one if needed)."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the global tracker (clears all data). Mainly for testing."""
        with cls._lock:
            cls._instance = None

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_seconds: float,
        cached_tokens: int = 0,
        conversation_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Record a single LLM API call."""
        # Clamp to non-negative to guard against garbage values
        input_tokens = max(0, input_tokens)
        output_tokens = max(0, output_tokens)
        latency_seconds = max(0.0, latency_seconds)

        cost = calculate_cost(model, input_tokens, output_tokens, cached_tokens)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cached_tokens": cached_tokens,
            "cost_usd": cost,
            "latency_seconds": round(latency_seconds, 3),
            "conversation_id": conversation_id,
        }
        if metadata:
            entry["metadata"] = dict(metadata)

        with self._data_lock:
            self._calls.append(entry)

        # Emit to analytics pipeline
        try:
            from bannin.analytics.pipeline import EventPipeline
            EventPipeline.get().emit({
                "type": "llm_call",
                "source": "llm",
                "severity": None,
                "message": f"LLM call: {model} ({input_tokens}in/{output_tokens}out, ${cost:.4f})",
                "data": {
                    "provider": provider,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost,
                    "latency_seconds": round(latency_seconds, 3),
                },
            })
        except Exception:
            logger.debug("Failed to emit LLM call to analytics pipeline")

    def get_summary(self) -> dict:
        """Get a full summary of all tracked LLM usage this session."""
        with self._data_lock:
            calls = list(self._calls)

        if not calls:
            return {
                "total_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "avg_latency_seconds": 0.0,
                "by_provider": {},
                "by_model": {},
                "session_duration_seconds": round(time.time() - self._session_start),
                "warnings": [],
            }

        total_input = sum(c["input_tokens"] for c in calls)
        total_output = sum(c["output_tokens"] for c in calls)
        total_cost = sum(c["cost_usd"] for c in calls)
        avg_latency = sum(c["latency_seconds"] for c in calls) / len(calls)

        # Group by provider
        by_provider = {}
        for c in calls:
            p = c["provider"]
            if p not in by_provider:
                by_provider[p] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
            by_provider[p]["calls"] += 1
            by_provider[p]["input_tokens"] += c["input_tokens"]
            by_provider[p]["output_tokens"] += c["output_tokens"]
            by_provider[p]["total_tokens"] += c["input_tokens"] + c["output_tokens"]
            by_provider[p]["cost_usd"] = round(by_provider[p]["cost_usd"] + c["cost_usd"], 6)

        # Group by model
        by_model = {}
        for c in calls:
            m = c["model"]
            if m not in by_model:
                by_model[m] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
            by_model[m]["calls"] += 1
            by_model[m]["input_tokens"] += c["input_tokens"]
            by_model[m]["output_tokens"] += c["output_tokens"]
            by_model[m]["total_tokens"] += c["input_tokens"] + c["output_tokens"]
            by_model[m]["cost_usd"] = round(by_model[m]["cost_usd"] + c["cost_usd"], 6)

        # Warnings
        warnings = self._generate_warnings(calls, total_cost)

        return {
            "total_calls": len(calls),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "total_cost_usd": round(total_cost, 4),
            "avg_latency_seconds": round(avg_latency, 3),
            "by_provider": by_provider,
            "by_model": by_model,
            "session_duration_seconds": round(time.time() - self._session_start),
            "warnings": warnings,
        }

    def get_calls(self, limit: int | None = None) -> list[dict]:
        """Get recent calls, newest first."""
        with self._data_lock:
            calls = [dict(c) for c in reversed(self._calls)]
        if limit is not None:
            limit = max(0, min(limit, len(calls)))
            calls = calls[:limit]
        return calls

    def get_context_usage(self, model: str, current_prompt_tokens: int) -> dict:
        """Predict context window exhaustion for a model.

        Args:
            model: The model name (to look up context window size)
            current_prompt_tokens: How many tokens are currently in the prompt
                (this is the prompt_tokens from the most recent API call)

        Returns dict with context window info and prediction.
        """
        context_window = get_context_window(model)
        if not context_window or context_window <= 0:
            return {
                "model": model,
                "context_window": None,
                "prompt_tokens": current_prompt_tokens,
                "percent_used": None,
                "note": f"Unknown model '{model}' — cannot predict context exhaustion.",
            }

        percent_used = round((current_prompt_tokens / context_window) * 100, 1)

        # Estimate messages remaining based on average output size
        with self._data_lock:
            all_calls = list(self._calls)
        model_calls = [c for c in all_calls if c["model"] == model]

        if model_calls:
            avg_tokens_per_turn = sum(c["total_tokens"] for c in model_calls) / len(model_calls)
        else:
            avg_tokens_per_turn = 1000  # rough default

        tokens_remaining = context_window - current_prompt_tokens
        estimated_messages_left = max(0, int(tokens_remaining / avg_tokens_per_turn)) if avg_tokens_per_turn > 0 else 0

        result = {
            "model": model,
            "context_window": context_window,
            "prompt_tokens": current_prompt_tokens,
            "tokens_remaining": max(0, tokens_remaining),
            "percent_used": percent_used,
            "estimated_messages_remaining": estimated_messages_left,
        }

        if percent_used >= 90:
            result["warning"] = f"CONTEXT CRITICAL: {percent_used}% used. ~{estimated_messages_left} messages left before context is full."
        elif percent_used >= 75:
            result["warning"] = f"CONTEXT HIGH: {percent_used}% used. Consider starting a new conversation."
        elif percent_used >= 50:
            result["note"] = f"Context is {percent_used}% full. ~{estimated_messages_left} messages estimated remaining."

        return result

    def get_latency_trend(self, model: str | None = None, last_n: int = 10) -> dict:
        """Check if response latency is increasing (sign of degradation)."""
        with self._data_lock:
            calls = list(self._calls)

        if model:
            calls = [c for c in calls if c["model"] == model]

        if len(calls) < 2:
            return {"trend": "insufficient_data", "data_points": len(calls)}

        recent = calls[-last_n:]
        latencies = [c["latency_seconds"] for c in recent]

        # Simple trend: compare first half vs second half
        mid = len(latencies) // 2
        first_half_avg = sum(latencies[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(latencies[mid:]) / (len(latencies) - mid) if len(latencies) > mid else 0

        if second_half_avg > first_half_avg * 1.5 and second_half_avg > 2.0:
            trend = "degrading"
            note = f"Latency increasing: {round(first_half_avg, 1)}s → {round(second_half_avg, 1)}s. Provider may be overloaded."
        elif second_half_avg < first_half_avg * 0.7:
            trend = "improving"
            note = f"Latency improving: {round(first_half_avg, 1)}s → {round(second_half_avg, 1)}s."
        else:
            trend = "stable"
            note = f"Latency stable at ~{round(sum(latencies) / len(latencies), 1)}s."

        return {
            "trend": trend,
            "note": note,
            "latest_latency": round(latencies[-1], 3),
            "avg_latency": round(sum(latencies) / len(latencies), 3),
            "data_points": len(latencies),
        }

    def get_health(self, session_fatigue: dict | None = None, vram_pressure: float | None = None, inference_trend: float | None = None, client_label: str | None = None) -> dict:
        """Compute unified health score from all available signals.

        Args:
            session_fatigue: Dict from MCPSessionTracker.get_session_health().
            vram_pressure: Ollama VRAM usage 0-100.
            inference_trend: Current tps / initial tps ratio.
            client_label: Override MCP client label (e.g., 'Claude Desktop').

        Returns:
            Full health dict with score, rating, components, recommendations.
        """
        from bannin.llm.health import calculate_health_score
        from bannin.llm.pricing import get_context_window

        with self._data_lock:
            calls = list(self._calls)

        # Derive context_percent from the most recent call's model,
        # or from MCP session token estimation if no API calls tracked
        context_percent = 0.0
        model = None
        if calls:
            latest = calls[-1]
            model = latest.get("model")
            if model:
                ctx_window = get_context_window(model)
                if ctx_window:
                    context_percent = min(100.0, (latest["input_tokens"] / ctx_window) * 100)

        # If no API calls but we have MCP session data, use estimated context
        if context_percent == 0.0 and session_fatigue:
            estimated = session_fatigue.get("estimated_context_percent", 0)
            if estimated > 0:
                context_percent = estimated

        # Derive latency_ratio from call history
        latency_ratio = None
        if len(calls) >= 4:
            latencies = [c["latency_seconds"] for c in calls]
            mid = len(latencies) // 2
            first_avg = sum(latencies[:mid]) / mid if mid > 0 else 0
            second_avg = sum(latencies[mid:]) / (len(latencies) - mid) if len(latencies) > mid else 0
            if first_avg > 0:
                latency_ratio = round(second_avg / first_avg, 2)

        # Derive cost_efficiency_trend
        cost_efficiency_trend = None
        if len(calls) >= 4:
            mid = len(calls) // 2
            first_half = calls[:mid]
            second_half = calls[mid:]
            first_cpo = self._avg_cost_per_output(first_half)
            second_cpo = self._avg_cost_per_output(second_half)
            if first_cpo and first_cpo > 0:
                cost_efficiency_trend = round(second_cpo / first_cpo, 2)

        return calculate_health_score(
            context_percent=context_percent,
            latency_ratio=latency_ratio,
            cost_efficiency_trend=cost_efficiency_trend,
            session_fatigue=session_fatigue,
            vram_pressure=vram_pressure,
            inference_trend=inference_trend,
            model=model,
            client_label=client_label,
        )

    def _avg_cost_per_output(self, calls: list[dict]) -> float:
        """Average cost per output token across a list of calls."""
        total_cost = sum(c["cost_usd"] for c in calls)
        total_output = sum(c["output_tokens"] for c in calls)
        if total_output == 0:
            return 0.0
        return total_cost / total_output

    def _generate_warnings(self, calls: list[dict], total_cost: float) -> list[str]:
        """Generate warnings based on usage patterns."""
        warnings = []

        # LLM-specific binary check: unknown model pricing
        unpriced = set()
        for c in calls:
            if c["cost_usd"] == 0.0 and c["total_tokens"] > 0:
                unpriced.add(c["model"])
        if unpriced:
            warnings.append(
                f"PRICING UNKNOWN: Cost could not be calculated for: {', '.join(sorted(unpriced))}. "
                f"Tokens are still tracked."
            )

        # Threshold-based warnings come from the central alert engine
        try:
            from bannin.intelligence.alerts import ThresholdEngine
            active = ThresholdEngine.get().get_active_alerts()
            for alert in active.get("active", []):
                # Only include LLM-related alerts here
                if alert["id"].startswith(("llm_", "context_", "latency_")):
                    warnings.append(alert["message"])
        except Exception:
            logger.debug("Failed to fetch active alerts for LLM warnings")

        return warnings


class track:
    """Context manager for creating a named tracking scope.

    Usage:
        with bannin.track("my-experiment"):
            response = client.chat.completions.create(...)
            # calls are tagged with this scope name
    """

    _current_scope = threading.local()

    def __init__(self, name: str = "default") -> None:
        self._name = name
        self._previous: str | None = None

    def __enter__(self) -> track:
        self._previous = getattr(track._current_scope, "name", None)
        track._current_scope.name = self._name
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> bool:
        track._current_scope.name = self._previous
        return False

    @classmethod
    def current_scope(cls) -> str | None:
        """Get the name of the current tracking scope, if any."""
        return getattr(cls._current_scope, "name", None)
