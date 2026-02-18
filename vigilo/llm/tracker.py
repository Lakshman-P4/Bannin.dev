"""LLM usage tracker — stores all API call data and provides summaries.

The tracker is a singleton that accumulates usage across the entire session.
"""

import threading
import time
from datetime import datetime, timezone

from vigilo.llm.pricing import calculate_cost, get_context_window, get_provider


class LLMTracker:
    """Central store for all LLM API call data."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._calls = []
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
    def reset(cls):
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
    ):
        """Record a single LLM API call."""
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
            entry["metadata"] = metadata

        with self._data_lock:
            self._calls.append(entry)

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
                by_provider[p] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            by_provider[p]["calls"] += 1
            by_provider[p]["input_tokens"] += c["input_tokens"]
            by_provider[p]["output_tokens"] += c["output_tokens"]
            by_provider[p]["cost_usd"] = round(by_provider[p]["cost_usd"] + c["cost_usd"], 6)

        # Group by model
        by_model = {}
        for c in calls:
            m = c["model"]
            if m not in by_model:
                by_model[m] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            by_model[m]["calls"] += 1
            by_model[m]["input_tokens"] += c["input_tokens"]
            by_model[m]["output_tokens"] += c["output_tokens"]
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
            calls = list(reversed(self._calls))
        if limit is not None:
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
        if context_window is None:
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
            model_calls = [c for c in self._calls if c["model"] == model]

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

    def _generate_warnings(self, calls: list[dict], total_cost: float) -> list[str]:
        """Generate warnings based on usage patterns."""
        warnings = []

        # Spend warning
        if total_cost > 10.0:
            warnings.append(f"SPEND HIGH: ${total_cost:.2f} spent this session across all LLM calls.")
        elif total_cost > 5.0:
            warnings.append(f"SPEND NOTICE: ${total_cost:.2f} spent this session.")

        # Latency degradation check (across all models)
        if len(calls) >= 5:
            recent = calls[-5:]
            latencies = [c["latency_seconds"] for c in recent]
            avg_recent = sum(latencies) / len(latencies)
            if avg_recent > 10.0:
                warnings.append(f"LATENCY HIGH: Average response time is {avg_recent:.1f}s over last 5 calls.")

        # Context window check — look at the most recent call per model
        seen_models = {}
        for c in reversed(calls):
            if c["model"] not in seen_models:
                seen_models[c["model"]] = c
        for model, last_call in seen_models.items():
            ctx = self.get_context_usage(model, last_call["input_tokens"])
            if ctx.get("percent_used") and ctx["percent_used"] >= 80:
                warnings.append(
                    f"CONTEXT WARNING ({model}): {ctx['percent_used']}% of context window used. "
                    f"~{ctx['estimated_messages_remaining']} messages remaining."
                )

        # Unknown model pricing warning
        unpriced = set()
        for c in calls:
            if c["cost_usd"] == 0.0 and c["total_tokens"] > 0:
                unpriced.add(c["model"])
        if unpriced:
            warnings.append(
                f"PRICING UNKNOWN: Cost could not be calculated for: {', '.join(sorted(unpriced))}. "
                f"Tokens are still tracked."
            )

        return warnings


class track:
    """Context manager for creating a named tracking scope.

    Usage:
        with vigilo.track("my-experiment"):
            response = client.chat.completions.create(...)
            # calls are tagged with this scope name
    """

    _current_scope = threading.local()

    def __init__(self, name: str = "default"):
        self._name = name

    def __enter__(self):
        self._previous = getattr(track._current_scope, "name", None)
        track._current_scope.name = self._name
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        track._current_scope.name = self._previous
        return False

    @classmethod
    def current_scope(cls) -> str | None:
        """Get the name of the current tracking scope, if any."""
        return getattr(cls._current_scope, "name", None)
