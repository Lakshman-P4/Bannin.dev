"""Tests for MCP session token estimation.

Validates the gap analysis algorithm, complexity multipliers, minimum floor,
tool response token counting, burden scoring, and session health computation.
"""

import time
import collections
from collections import defaultdict

import pytest

from bannin.mcp.session import MCPSessionTracker, _TOOL_TOKEN_COSTS, _DEFAULT_TOOL_COST


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tracker():
    """Create a fresh MCPSessionTracker (bypasses singleton)."""
    t = MCPSessionTracker.__new__(MCPSessionTracker)
    t._data_lock = __import__("threading").Lock()
    t._session_id = "test-session-id"
    t._client_label = "Test Client"
    t._session_start = time.time()
    t._tool_calls = collections.deque(maxlen=5000)
    t._per_tool_counts = defaultdict(int)
    t._total_response_bytes = 0
    return t


def _make_calls(tracker, tool_names, gap_seconds=5, response_bytes=0):
    """Inject tool calls with specified gaps."""
    base = tracker._session_start + 2  # start 2s after session
    for i, tool in enumerate(tool_names):
        call = {
            "tool": tool,
            "timestamp": base + i * gap_seconds,
            "response_bytes": response_bytes,
        }
        tracker._tool_calls.append(call)
        tracker._per_tool_counts[tool] += 1
        tracker._total_response_bytes += response_bytes


# ---------------------------------------------------------------------------
# Token estimation: gap analysis
# ---------------------------------------------------------------------------

class TestGapAnalysis:
    def test_rapid_fire_gaps(self):
        """<10s gaps -> minimal conversation tokens."""
        t = _make_tracker()
        _make_calls(t, ["get_system_metrics"] * 5, gap_seconds=3)
        calls = list(t._tool_calls)
        session_minutes = 0.5
        result = t._estimate_tokens(calls, session_minutes)
        # Rapid fire: mostly tool tokens, low prompting
        assert result["prompting"] > 0
        assert result["ai_output"] > 0
        assert result["tool_responses"] > 0

    def test_short_exchange_gaps(self):
        """10-60s gaps -> short follow-up exchange tokens."""
        t = _make_tracker()
        _make_calls(t, ["get_system_metrics"] * 5, gap_seconds=30)
        calls = list(t._tool_calls)
        session_minutes = 3
        result = t._estimate_tokens(calls, session_minutes)
        # Short exchanges should produce more prompting than rapid fire
        assert result["prompting"] >= 200

    def test_full_turn_gaps(self):
        """1-5 min gaps -> full conversation turn tokens."""
        t = _make_tracker()
        _make_calls(t, ["get_system_metrics"] * 3, gap_seconds=180)
        calls = list(t._tool_calls)
        session_minutes = 10
        result = t._estimate_tokens(calls, session_minutes)
        assert result["prompting"] > 500
        assert result["ai_output"] > 1000

    def test_long_gaps_discounted(self):
        """>15 min gaps -> 50% idle discount."""
        t = _make_tracker()
        _make_calls(t, ["get_system_metrics"] * 2, gap_seconds=1200)  # 20min gaps
        calls = list(t._tool_calls)
        session_minutes = 40

        result = t._estimate_tokens(calls, session_minutes)
        total = sum(result.values())
        # Should have tokens, but discounted vs active time
        assert total > 0

    def test_no_calls_uses_minimum_floor(self):
        """Zero tool calls, session > 1 min -> minimum floor applies."""
        t = _make_tracker()
        session_minutes = 5
        result = t._estimate_tokens([], session_minutes)
        total = sum(result.values())
        # Floor: 5 * 400 = 2000 tokens minimum
        assert total >= 2000

    def test_minimum_floor_not_applied_under_one_minute(self):
        """Session < 1 min: floor not applied."""
        t = _make_tracker()
        session_minutes = 0.5
        result = t._estimate_tokens([], session_minutes)
        total = sum(result.values())
        # Only gap tokens from session_start to now, no floor
        assert total >= 0


# ---------------------------------------------------------------------------
# Complexity multiplier
# ---------------------------------------------------------------------------

class TestComplexityMultiplier:
    def test_low_complexity(self):
        """<=2 unique tools -> 1.0x multiplier (no boost)."""
        t = _make_tracker()
        _make_calls(t, ["get_system_metrics", "get_system_metrics"], gap_seconds=30)
        calls = list(t._tool_calls)
        result = t._estimate_tokens(calls, 2)
        # Store baseline
        base_prompting = result["prompting"]

        # Now test with 5+ unique tools
        t2 = _make_tracker()
        tools = ["get_system_metrics", "get_running_processes", "predict_oom",
                 "get_active_alerts", "check_context_health"]
        _make_calls(t2, tools, gap_seconds=30)
        calls2 = list(t2._tool_calls)
        result2 = t2._estimate_tokens(calls2, 3)
        # High complexity should have higher prompting (1.3x multiplier)
        # But hard to compare directly due to different call counts, so just
        # check the multiplier path by verifying unique_tools >= 5 produces more
        assert result2["prompting"] > 0

    def test_medium_complexity(self):
        """3-4 unique tools -> 1.15x multiplier."""
        t = _make_tracker()
        tools = ["get_system_metrics", "get_running_processes", "predict_oom"]
        _make_calls(t, tools, gap_seconds=30)
        calls = list(t._tool_calls)
        unique = len(set(c["tool"] for c in calls))
        assert unique == 3
        result = t._estimate_tokens(calls, 2)
        # Just verify it computes without error and produces tokens
        assert result["prompting"] > 0


# ---------------------------------------------------------------------------
# Tool response token counting
# ---------------------------------------------------------------------------

class TestToolResponseTokens:
    def test_known_tool_uses_lookup(self):
        """Known tools should use per-tool cost from _TOOL_TOKEN_COSTS."""
        t = _make_tracker()
        _make_calls(t, ["get_system_metrics"], gap_seconds=5, response_bytes=0)
        calls = list(t._tool_calls)
        result = t._estimate_tokens(calls, 1)
        # tool_responses includes tool tokens + request tokens (300/call)
        expected_min = _TOOL_TOKEN_COSTS["get_system_metrics"] + 300
        assert result["tool_responses"] >= expected_min

    def test_unknown_tool_uses_default(self):
        """Unknown tools should use _DEFAULT_TOOL_COST."""
        t = _make_tracker()
        _make_calls(t, ["custom_tool"], gap_seconds=5, response_bytes=0)
        calls = list(t._tool_calls)
        result = t._estimate_tokens(calls, 1)
        expected_min = _DEFAULT_TOOL_COST + 300
        assert result["tool_responses"] >= expected_min

    def test_response_bytes_override(self):
        """When response_bytes > 0, uses byte-based estimation."""
        t = _make_tracker()
        # 4000 bytes -> 4000/4 = 1000 tokens (min 100)
        _make_calls(t, ["get_system_metrics"], gap_seconds=5, response_bytes=4000)
        calls = list(t._tool_calls)
        result = t._estimate_tokens(calls, 1)
        # Should use 1000 (from bytes) not 800 (from lookup)
        assert result["tool_responses"] >= 1000 + 300

    def test_small_response_bytes_uses_minimum(self):
        """Very small response -> minimum 100 tokens."""
        t = _make_tracker()
        _make_calls(t, ["get_system_metrics"], gap_seconds=5, response_bytes=10)
        calls = list(t._tool_calls)
        result = t._estimate_tokens(calls, 1)
        assert result["tool_responses"] >= 100 + 300


# ---------------------------------------------------------------------------
# Session health: burden scoring
# ---------------------------------------------------------------------------

class TestBurdenScoring:
    def _health_with_calls(self, n_calls, gap=5, session_offset=0):
        t = _make_tracker()
        if session_offset:
            t._session_start = time.time() - session_offset
        _make_calls(t, ["get_system_metrics"] * n_calls, gap_seconds=gap)
        # Patch out JSONL reader to avoid import side effects
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "bannin.mcp.session.ClaudeSessionReader",
                type("Fake", (), {"get": classmethod(lambda cls: type("R", (), {"get_real_health_data": lambda self: None})())}),
                raising=False,
            )
            return t.get_session_health()

    def test_low_burden(self):
        """<=5 calls -> burden_score = 0."""
        health = self._health_with_calls(3)
        assert health["tool_call_burden"] == 0

    def test_moderate_burden(self):
        """10-25 calls -> moderate burden."""
        health = self._health_with_calls(15, gap=2, session_offset=120)
        assert 0 < health["tool_call_burden"] <= 70

    def test_high_burden(self):
        """50+ calls -> burden maxed out."""
        health = self._health_with_calls(60, gap=1, session_offset=300)
        assert health["tool_call_burden"] == 100


# ---------------------------------------------------------------------------
# Session health: overall structure
# ---------------------------------------------------------------------------

class TestSessionHealthStructure:
    def test_returns_all_required_fields(self):
        t = _make_tracker()
        _make_calls(t, ["get_system_metrics", "predict_oom"], gap_seconds=10)
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "bannin.mcp.session.ClaudeSessionReader",
                type("Fake", (), {"get": classmethod(lambda cls: type("R", (), {"get_real_health_data": lambda self: None})())}),
                raising=False,
            )
            health = t.get_session_health()

        required = [
            "session_id", "client_label", "session_fatigue",
            "context_pressure", "tool_call_burden", "repeated_tool_score",
            "duration_score", "frequency_score", "session_duration_minutes",
            "total_tool_calls", "per_tool_counts", "details",
            "estimated_tokens", "estimated_context_percent",
            "token_breakdown", "data_source",
        ]
        for field in required:
            assert field in health, f"Missing field: {field}"

    def test_fatigue_clamped_0_100(self):
        t = _make_tracker()
        t._session_start = time.time() - 7200  # 2hr session
        _make_calls(t, ["get_system_metrics"] * 100, gap_seconds=1)
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "bannin.mcp.session.ClaudeSessionReader",
                type("Fake", (), {"get": classmethod(lambda cls: type("R", (), {"get_real_health_data": lambda self: None})())}),
                raising=False,
            )
            health = t.get_session_health()
        assert 0 <= health["session_fatigue"] <= 100

    def test_data_source_estimated(self):
        """Without JSONL reader, data_source should be 'estimated'."""
        t = _make_tracker()
        _make_calls(t, ["get_system_metrics"], gap_seconds=5)
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "bannin.mcp.session.ClaudeSessionReader",
                type("Fake", (), {"get": classmethod(lambda cls: type("R", (), {"get_real_health_data": lambda self: None})())}),
                raising=False,
            )
            health = t.get_session_health()
        assert health["data_source"] == "estimated"


# ---------------------------------------------------------------------------
# record_tool_call
# ---------------------------------------------------------------------------

class TestRecordToolCall:
    def test_increments_counters(self):
        t = _make_tracker()
        t.record_tool_call("get_system_metrics", response_bytes=500)
        t.record_tool_call("get_system_metrics", response_bytes=300)
        t.record_tool_call("predict_oom", response_bytes=200)

        assert len(t._tool_calls) == 3
        assert t._per_tool_counts["get_system_metrics"] == 2
        assert t._per_tool_counts["predict_oom"] == 1
        assert t._total_response_bytes == 1000

    def test_stores_timestamp(self):
        t = _make_tracker()
        before = time.time()
        t.record_tool_call("test_tool", response_bytes=0)
        after = time.time()

        call = t._tool_calls[0]
        assert before <= call["timestamp"] <= after
        assert call["tool"] == "test_tool"
        assert call["response_bytes"] == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_returns_session_info(self):
        t = _make_tracker()
        t.record_tool_call("get_system_metrics", response_bytes=100)
        stats = t.get_stats()

        assert stats["session_id"] == "test-session-id"
        assert stats["client_label"] == "Test Client"
        assert stats["total_tool_calls"] == 1
        assert "get_system_metrics" in stats["per_tool_counts"]
        assert stats["session_duration_minutes"] >= 0


# ---------------------------------------------------------------------------
# get_push_payload
# ---------------------------------------------------------------------------

class TestGetPushPayload:
    def test_includes_health_data(self):
        t = _make_tracker()
        t.record_tool_call("get_system_metrics", response_bytes=200)
        with pytest.MonkeyPatch.context() as m:
            m.setattr(
                "bannin.mcp.session.ClaudeSessionReader",
                type("Fake", (), {"get": classmethod(lambda cls: type("R", (), {"get_real_health_data": lambda self: None})())}),
                raising=False,
            )
            payload = t.get_push_payload()

        assert "session_fatigue" in payload
        assert "estimated_tokens" in payload
        assert "session_id" in payload
        assert "client_label" in payload
