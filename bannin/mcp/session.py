"""MCP session health tracker -- monitors AI coding tool cognitive state.

Tracks every MCP tool call and estimates overall conversation token consumption
to detect session fatigue, context degradation, and repeated tool patterns.
Provides a session health score that feeds into the unified health system.

Token estimation model:
We can't see the actual conversation, but we CAN observe tool call patterns
(names, timing, response sizes, gaps) and use them to infer what's happening.

Key signals:
- Tool response sizes: measured directly (actual tokens we contribute)
- Gap analysis: time between tool calls reveals conversation activity
  - <10s gap = AI rapid-firing tools, minimal user interaction (~100 tokens)
  - 10-60s gap = short follow-up exchange (~500 tokens)
  - 1-5 min gap = full conversation turn with prompting + response (~2500 tokens)
  - 5-15 min gap = multi-turn complex task (planning, debugging) (~6000 tokens)
  - >15 min gap = likely includes idle time (50% discount)
- Tool diversity: more unique tools = complex multi-step task = higher context
- Prompt complexity: inferred from which tools are called and in what order
  - Simple check (get_system_metrics alone) = low complexity
  - Investigation (metrics + processes + alerts) = moderate complexity
  - Deep analysis (health + recommendations + history) = high complexity
"""

import threading
import time
import uuid
from collections import defaultdict
from typing import Optional


# Estimated tokens per tool response (measured from typical JSON payloads)
_TOOL_TOKEN_COSTS: dict[str, int] = {
    "get_system_metrics": 800,       # full system snapshot JSON
    "get_running_processes": 1200,    # process list with details
    "predict_oom": 600,              # prediction result
    "get_training_status": 500,      # task list
    "get_active_alerts": 400,        # alert list
    "check_context_health": 1000,    # health score + components
    "get_recommendations": 1500,     # multiple recommendations
    "query_history": 2000,           # event history results
    "search_events": 1500,           # search results
}
_DEFAULT_TOOL_COST = 800  # fallback for unknown tools


class MCPSessionTracker:
    """Singleton that records MCP tool calls and computes session fatigue."""

    _instance: Optional["MCPSessionTracker"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._data_lock = threading.Lock()
        self._session_id: str = str(uuid.uuid4())
        self._client_label: str = "Unknown MCP Client"
        self._session_start = time.time()
        self._tool_calls: list[dict] = []
        self._per_tool_counts: dict[str, int] = defaultdict(int)
        self._total_response_bytes: int = 0

    @classmethod
    def get(cls) -> "MCPSessionTracker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._instance = None

    def set_client_label(self, label: str):
        """Set the detected parent client label (e.g., 'Claude Desktop')."""
        self._client_label = label

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def client_label(self) -> str:
        return self._client_label

    def record_tool_call(self, tool_name: str, response_bytes: int = 0):
        """Record a single MCP tool invocation.

        Args:
            tool_name: Name of the tool called.
            response_bytes: Size of the JSON response in bytes (0 if unknown).
        """
        now = time.time()
        with self._data_lock:
            self._tool_calls.append({
                "tool": tool_name,
                "timestamp": now,
                "response_bytes": response_bytes,
            })
            self._per_tool_counts[tool_name] += 1
            self._total_response_bytes += response_bytes

        # Emit analytics event
        try:
            from bannin.analytics.pipeline import EventPipeline
            EventPipeline.get().emit({
                "type": "mcp_tool_call",
                "source": "mcp",
                "severity": None,
                "message": f"MCP tool call: {tool_name}",
                "data": {"tool": tool_name},
            })
        except Exception:
            pass

    def _estimate_tokens(self, calls: list[dict], session_minutes: float) -> dict:
        """Estimate total token consumption from observable signals.

        Returns breakdown: tool_responses, prompting, ai_output, thinking.
        """
        now = time.time()
        total_calls = len(calls)

        # --- 1. Tool response tokens (most accurate -- measured or per-tool estimate) ---
        tool_tokens = 0
        for c in calls:
            rbytes = c.get("response_bytes", 0)
            if rbytes > 0:
                # ~4 chars per token for JSON
                tool_tokens += max(100, rbytes // 4)
            else:
                tool_tokens += _TOOL_TOKEN_COSTS.get(c["tool"], _DEFAULT_TOOL_COST)

        # Tool request tokens (schema + parameters, relatively fixed)
        tool_request_tokens = total_calls * 300

        # --- 2. Gap analysis: estimate conversation between tool calls ---
        # Each gap represents user prompting + AI response happening outside our view
        prompting_tokens = 0
        ai_output_tokens = 0
        thinking_tokens = 0

        timestamps = [self._session_start] + [c["timestamp"] for c in calls] + [now]

        for i in range(len(timestamps) - 1):
            gap_seconds = timestamps[i + 1] - timestamps[i]
            gap_minutes = gap_seconds / 60

            if gap_seconds < 10:
                # Rapid tool calls -- AI is executing, minimal conversation
                prompting_tokens += 50
                ai_output_tokens += 100
                thinking_tokens += 50
            elif gap_seconds < 60:
                # Short exchange -- quick follow-up or clarification
                prompting_tokens += 200
                ai_output_tokens += 400
                thinking_tokens += 150
            elif gap_minutes < 5:
                # Full conversation turn -- user prompted, AI responded with substance
                # Longer gap = more complex exchange
                intensity = min(1.5, gap_minutes / 3)
                prompting_tokens += int(800 * intensity)
                ai_output_tokens += int(1500 * intensity)
                thinking_tokens += int(500 * intensity)
            elif gap_minutes < 15:
                # Multi-turn complex task (planning, debugging, code review)
                prompting_tokens += int(1500 + gap_minutes * 100)
                ai_output_tokens += int(3000 + gap_minutes * 200)
                thinking_tokens += int(800 + gap_minutes * 80)
            else:
                # Long gap -- likely includes idle time. Discount by 50%.
                active_minutes = gap_minutes * 0.5
                prompting_tokens += int(active_minutes * 400)
                ai_output_tokens += int(active_minutes * 800)
                thinking_tokens += int(active_minutes * 200)

        # --- 3. Complexity multiplier ---
        # More unique tools = investigating from multiple angles = complex session
        unique_tools = len(set(c["tool"] for c in calls)) if calls else 0
        if unique_tools >= 5:
            complexity_mult = 1.3
        elif unique_tools >= 3:
            complexity_mult = 1.15
        else:
            complexity_mult = 1.0

        prompting_tokens = int(prompting_tokens * complexity_mult)
        ai_output_tokens = int(ai_output_tokens * complexity_mult)

        # --- 4. Minimum floor based on session duration ---
        # Even with 0 tool calls, a session has conversation activity.
        # Typical Claude Code session: ~600-1000 tokens/minute when active.
        min_tokens = int(session_minutes * 400)  # conservative floor
        current_total = (tool_tokens + tool_request_tokens + prompting_tokens
                         + ai_output_tokens + thinking_tokens)
        if current_total < min_tokens and session_minutes > 1:
            # Scale up proportionally to hit minimum
            gap = min_tokens - current_total
            prompting_tokens += int(gap * 0.35)
            ai_output_tokens += int(gap * 0.45)
            thinking_tokens += int(gap * 0.20)

        return {
            "tool_responses": tool_tokens + tool_request_tokens,
            "prompting": prompting_tokens,
            "ai_output": ai_output_tokens,
            "thinking": thinking_tokens,
        }

    def get_session_health(self) -> dict:
        """Compute session fatigue score from tool call patterns and token estimates.

        Returns dict with:
            session_fatigue: 0-100 (0 = fresh, 100 = exhausted)
            tool_call_burden: 0-100
            repeated_tool_score: 0-100
            session_duration_minutes: float
            total_tool_calls: int
            estimated_tokens: int
            estimated_context_percent: float
            details: str
        """
        with self._data_lock:
            calls = list(self._tool_calls)
            per_tool = dict(self._per_tool_counts)

        now = time.time()
        session_minutes = (now - self._session_start) / 60
        total_calls = len(calls)

        # --- Component 1: Tool call burden ---
        if total_calls <= 5:
            burden_score = 0
        elif total_calls <= 10:
            burden_score = (total_calls - 5) * 4
        elif total_calls <= 25:
            burden_score = 20 + (total_calls - 10) * 3.3
        elif total_calls <= 50:
            burden_score = 70 + (total_calls - 25) * 1.2
        else:
            burden_score = 100
        burden_score = min(100, burden_score)

        # --- Component 2: Repeated tool detection ---
        recent_cutoff = now - 60
        recent_calls = [c for c in calls if c["timestamp"] >= recent_cutoff]
        recent_by_tool: dict[str, int] = defaultdict(int)
        for c in recent_calls:
            recent_by_tool[c["tool"]] += 1

        max_repeat = max(recent_by_tool.values()) if recent_by_tool else 0
        if max_repeat <= 2:
            repeat_score = 0
        elif max_repeat <= 4:
            repeat_score = (max_repeat - 2) * 25
        elif max_repeat <= 6:
            repeat_score = 50 + (max_repeat - 4) * 15
        else:
            repeat_score = min(100, 80 + (max_repeat - 6) * 10)

        # --- Component 3: Session duration penalty ---
        if session_minutes <= 15:
            duration_score = 0
        elif session_minutes <= 30:
            duration_score = (session_minutes - 15) * 1.33
        elif session_minutes <= 60:
            duration_score = 20 + (session_minutes - 30) * 1.33
        elif session_minutes <= 120:
            duration_score = 60 + (session_minutes - 60) * 0.67
        else:
            duration_score = 100
        duration_score = min(100, duration_score)

        # --- Component 4: Tool call frequency trend ---
        frequency_score = 0
        if total_calls >= 6:
            mid_time = self._session_start + (now - self._session_start) / 2
            first_half = [c for c in calls if c["timestamp"] < mid_time]
            second_half = [c for c in calls if c["timestamp"] >= mid_time]

            half_duration = (now - self._session_start) / 2 / 60
            if half_duration > 0:
                first_rate = len(first_half) / half_duration
                second_rate = len(second_half) / half_duration
                if first_rate > 0:
                    accel_ratio = second_rate / first_rate
                    if accel_ratio > 2.0:
                        frequency_score = min(100, (accel_ratio - 1) * 50)
                    elif accel_ratio > 1.5:
                        frequency_score = (accel_ratio - 1) * 40

        # --- Token estimation (fallback when JSONL data unavailable) ---
        token_breakdown = self._estimate_tokens(calls, session_minutes)
        estimated_tokens = sum(token_breakdown.values())

        # Context usage against model window
        context_window = 200000
        estimated_context_percent = min(100.0, round(
            (estimated_tokens / context_window) * 100, 1))

        # --- Override with real JSONL data if available ---
        data_source = "estimated"
        real_session_data = None
        try:
            from bannin.llm.claude_session import ClaudeSessionReader
            rd = ClaudeSessionReader.get().get_real_health_data()
            if rd:
                data_source = "real"
                real_session_data = rd
                estimated_tokens = rd["context_tokens"]
                estimated_context_percent = rd["context_percent"]
                context_window = rd["context_window"]
                token_breakdown = {
                    "context_window_tokens": rd["context_tokens"],
                    "output_generated": rd["total_output_tokens"],
                    "thinking": rd["estimated_thinking_tokens"],
                    "cache_read": rd["total_cache_read_tokens"],
                    "cache_write": rd["total_cache_write_tokens"],
                }
                # Use real session duration from JSONL timestamps instead of
                # MCP server uptime (which resets on MCP restart)
                real_duration = rd.get("session_duration_seconds", 0)
                if real_duration > 0:
                    session_minutes = real_duration / 60
                    # Recalculate duration_score with real duration
                    if session_minutes <= 15:
                        duration_score = 0
                    elif session_minutes <= 30:
                        duration_score = (session_minutes - 15) * 1.33
                    elif session_minutes <= 60:
                        duration_score = 20 + (session_minutes - 30) * 1.33
                    elif session_minutes <= 120:
                        duration_score = 60 + (session_minutes - 60) * 0.67
                    else:
                        duration_score = 100
                    duration_score = min(100, duration_score)
        except Exception:
            pass

        # --- Component 5: Context pressure ---
        cp = estimated_context_percent
        if cp <= 15:
            context_pressure = 0
        elif cp <= 30:
            context_pressure = (cp - 15) * 2.0
        elif cp <= 50:
            context_pressure = 30 + (cp - 30) * 2.0
        elif cp <= 75:
            context_pressure = 70 + (cp - 50) * 1.2
        else:
            context_pressure = 100
        context_pressure = min(100, context_pressure)

        # --- Weighted fatigue score ---
        fatigue = (
            context_pressure * 0.35
            + duration_score * 0.30
            + burden_score * 0.15
            + repeat_score * 0.10
            + frequency_score * 0.10
        )
        fatigue = round(min(100, max(0, fatigue)), 1)

        # Build detail message
        details = []
        if data_source == "real" and real_session_data:
            ctx = real_session_data["context_tokens"]
            pct = real_session_data["context_percent"]
            msgs = real_session_data["total_messages"]
            if ctx >= 1000:
                details.append(f"{ctx // 1000}k tokens in context ({pct:.0f}% used)")
            details.append(f"{msgs} messages")
        elif estimated_tokens > 0:
            if estimated_tokens >= 100000:
                details.append(f"~{estimated_tokens // 1000}k tokens estimated ({estimated_context_percent:.0f}% context)")
            elif estimated_tokens >= 1000:
                details.append(f"~{estimated_tokens // 1000}k tokens estimated")
        if burden_score >= 50:
            details.append(f"{total_calls} tool calls (high burden)")
        if repeat_score >= 50:
            most_repeated = max(recent_by_tool, key=recent_by_tool.get) if recent_by_tool else ""
            details.append(f"'{most_repeated}' called {max_repeat}x in last 60s")
        if duration_score >= 40:
            details.append(f"session running {session_minutes:.0f} minutes")
        if frequency_score >= 30:
            details.append("tool call frequency accelerating")

        detail_str = "; ".join(details) if details else "Session is fresh"

        result = {
            "session_id": self._session_id,
            "client_label": self._client_label,
            "session_fatigue": fatigue,
            "context_pressure": round(context_pressure, 1),
            "tool_call_burden": round(burden_score, 1),
            "repeated_tool_score": round(repeat_score, 1),
            "duration_score": round(duration_score, 1),
            "frequency_score": round(frequency_score, 1),
            "session_duration_minutes": round(session_minutes, 1),
            "total_tool_calls": total_calls,
            "per_tool_counts": per_tool,
            "details": detail_str,
            "estimated_tokens": estimated_tokens,
            "estimated_context_percent": estimated_context_percent,
            "token_breakdown": token_breakdown,
            "data_source": data_source,
        }
        if real_session_data:
            result["real_session_data"] = real_session_data
        return result

    def get_stats(self) -> dict:
        """Raw session metrics for MCP tool responses."""
        with self._data_lock:
            per_tool = dict(self._per_tool_counts)
            total = len(self._tool_calls)

        return {
            "session_id": self._session_id,
            "client_label": self._client_label,
            "session_start": self._session_start,
            "session_duration_minutes": round((time.time() - self._session_start) / 60, 1),
            "total_tool_calls": total,
            "per_tool_counts": per_tool,
        }

    def get_push_payload(self) -> dict:
        """Full payload for pushing to the agent, including identity and health."""
        health = self.get_session_health()
        return health
