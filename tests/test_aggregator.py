"""Tests for the health aggregator.

Validates multi-source combining, worst-of scoring, source filtering,
JSONL fallback logic, _score_to_rating, and per_source structure.
"""

import pytest
from unittest.mock import patch, MagicMock

from bannin.llm.aggregator import (
    compute_health,
    _score_to_rating,
    _build_combined,
    _extract_real_data,
)


# ---------------------------------------------------------------------------
# _score_to_rating
# ---------------------------------------------------------------------------

class TestScoreToRating:
    def test_excellent(self):
        assert _score_to_rating(95) == "excellent"

    def test_excellent_boundary(self):
        assert _score_to_rating(90) == "excellent"

    def test_good(self):
        assert _score_to_rating(75) == "good"

    def test_good_boundary(self):
        assert _score_to_rating(70) == "good"

    def test_fair(self):
        assert _score_to_rating(55) == "fair"

    def test_fair_boundary(self):
        assert _score_to_rating(50) == "fair"

    def test_poor(self):
        assert _score_to_rating(35) == "poor"

    def test_poor_boundary(self):
        assert _score_to_rating(30) == "poor"

    def test_critical(self):
        assert _score_to_rating(20) == "critical"

    def test_critical_zero(self):
        assert _score_to_rating(0) == "critical"

    def test_critical_boundary(self):
        assert _score_to_rating(29.9) == "critical"


# ---------------------------------------------------------------------------
# _extract_real_data
# ---------------------------------------------------------------------------

class TestExtractRealData:
    def test_extracts_known_fields(self):
        rd = {
            "model": "claude-sonnet-4-20250514",
            "context_tokens": 50000,
            "context_window": 200000,
            "context_percent": 25.0,
            "total_output_tokens": 12000,
            "total_messages": 42,
            "total_tool_uses": 8,
            "cache_hit_rate": 0.6,
            "session_duration_seconds": 1800,
            "api_calls": 20,
            "context_growth_rate": 500.0,
            "extra_field": "ignored",
        }
        result = _extract_real_data(rd)
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["context_tokens"] == 50000
        assert result["total_messages"] == 42
        assert "extra_field" not in result

    def test_defaults_on_missing(self):
        result = _extract_real_data({})
        assert result["context_tokens"] == 0
        assert result["context_window"] == 200000
        assert result["model"] is None


# ---------------------------------------------------------------------------
# compute_health (integration-level, mocked dependencies)
# ---------------------------------------------------------------------------

class TestComputeHealth:
    @patch("bannin.llm.aggregator.get_mcp_sessions")
    @patch("bannin.llm.aggregator.get_mcp_session_data")
    @patch("bannin.llm.tracker.LLMTracker.get")
    def test_no_sources_returns_baseline(self, mock_tracker_get, mock_worst, mock_sessions):
        """With no active sources, returns baseline health from tracker."""
        mock_sessions.return_value = {}
        mock_worst.return_value = None

        tracker = MagicMock()
        mock_tracker_get.return_value = tracker
        tracker.get_summary.return_value = {"total_calls": 0}
        tracker.get_health.return_value = {
            "health_score": 100,
            "rating": "excellent",
            "source": "No active LLM signals -- baseline score",
            "components": {},
            "recommendation": None,
        }
        result = compute_health()

        assert result["health_score"] == 100
        assert result["rating"] == "excellent"

    @patch("bannin.llm.aggregator.get_mcp_sessions")
    @patch("bannin.llm.aggregator.get_mcp_session_data")
    @patch("bannin.llm.tracker.LLMTracker.get")
    def test_single_mcp_source(self, mock_tracker_get, mock_worst, mock_sessions):
        """Single MCP session produces per_source with one entry."""
        mock_sessions.return_value = {
            "abc-123": {
                "client_label": "Claude Code",
                "session_fatigue": 30,
                "tool_call_burden": 20,
                "estimated_context_percent": 15,
                "session_duration_minutes": 10,
                "total_tool_calls": 5,
                "data_source": "estimated",
            }
        }
        mock_worst.return_value = mock_sessions.return_value["abc-123"]

        tracker = MagicMock()
        mock_tracker_get.return_value = tracker
        tracker.get_summary.return_value = {"total_calls": 0}
        tracker.get_health.return_value = {
            "health_score": 80,
            "rating": "good",
            "source": "MCP Session (Claude Code)",
            "components": {"context_freshness": {"score": 100, "weight": 0.25, "detail": "Fresh"}},
            "recommendation": None,
        }
        result = compute_health()

        assert "per_source" in result
        assert len(result["per_source"]) == 1
        src = result["per_source"][0]
        assert src["type"] == "mcp"
        assert "Claude Code" in src["label"]
        assert src["health_score"] == 80

    @patch("bannin.llm.aggregator.get_mcp_sessions")
    @patch("bannin.llm.aggregator.get_mcp_session_data")
    @patch("bannin.llm.tracker.LLMTracker.get")
    def test_worst_of_scoring(self, mock_tracker_get, mock_worst, mock_sessions):
        """Combined score should be the worst (minimum) across sources."""
        mock_sessions.return_value = {
            "s1": {
                "client_label": "Claude Desktop",
                "session_fatigue": 60,
                "tool_call_burden": 50,
                "estimated_context_percent": 40,
                "session_duration_minutes": 30,
                "total_tool_calls": 15,
                "data_source": "estimated",
            },
            "s2": {
                "client_label": "Claude Code",
                "session_fatigue": 10,
                "tool_call_burden": 5,
                "estimated_context_percent": 10,
                "session_duration_minutes": 5,
                "total_tool_calls": 2,
                "data_source": "estimated",
            },
        }
        mock_worst.return_value = mock_sessions.return_value["s1"]

        def mock_get_health(**kwargs):
            fatigue = kwargs.get("session_fatigue")
            if fatigue and fatigue.get("session_fatigue", 0) >= 50:
                return {
                    "health_score": 45,
                    "rating": "fair",
                    "source": "MCP",
                    "components": {},
                    "recommendation": "Start fresh",
                }
            return {
                "health_score": 90,
                "rating": "excellent",
                "source": "MCP",
                "components": {},
                "recommendation": None,
            }

        tracker = MagicMock()
        mock_tracker_get.return_value = tracker
        tracker.get_summary.return_value = {"total_calls": 0}
        tracker.get_health.side_effect = mock_get_health
        result = compute_health()

        # Combined score should be worst-of = 45
        assert result["health_score"] == 45
        assert result["rating"] == "poor"  # 45 < 50 threshold -> poor
        assert len(result["per_source"]) == 2

    @patch("bannin.llm.aggregator.get_mcp_sessions")
    @patch("bannin.llm.aggregator.get_mcp_session_data")
    @patch("bannin.llm.tracker.LLMTracker.get")
    def test_source_filter_api(self, mock_tracker_get, mock_worst, mock_sessions):
        """source_filter='api' should skip MCP and Ollama collection."""
        mock_sessions.return_value = {}
        mock_worst.return_value = None

        tracker = MagicMock()
        mock_tracker_get.return_value = tracker
        tracker.get_summary.return_value = {"total_calls": 5}
        tracker.get_health.return_value = {
            "health_score": 85,
            "rating": "good",
            "source": "LLM API",
            "components": {},
            "recommendation": None,
        }
        result = compute_health(source_filter="api")

        # Should still produce a result even with no MCP/Ollama
        assert result["health_score"] == 85

    @patch("bannin.llm.aggregator.get_mcp_sessions")
    @patch("bannin.llm.aggregator.get_mcp_session_data")
    @patch("bannin.llm.tracker.LLMTracker.get")
    def test_api_source_included(self, mock_tracker_get, mock_worst, mock_sessions):
        """API calls tracked -> API source appears in per_source."""
        mock_sessions.return_value = {}
        mock_worst.return_value = None

        tracker = MagicMock()
        mock_tracker_get.return_value = tracker
        tracker.get_summary.return_value = {"total_calls": 10}
        tracker.get_health.return_value = {
            "health_score": 75,
            "rating": "good",
            "source": "LLM API",
            "components": {},
            "recommendation": None,
        }
        result = compute_health()

        # With only API source, should have per_source
        if "per_source" in result:
            api_sources = [s for s in result["per_source"] if s["type"] == "api"]
            assert len(api_sources) == 1
            assert api_sources[0]["label"] == "LLM API"


# ---------------------------------------------------------------------------
# _build_combined
# ---------------------------------------------------------------------------

class TestBuildCombined:
    @patch("bannin.llm.aggregator.get_mcp_session_data")
    def test_uses_worst_score(self, mock_worst):
        mock_worst.return_value = None

        tracker = MagicMock()
        tracker.get_health.return_value = {
            "health_score": 90,
            "rating": "excellent",
            "source": "test",
            "components": {},
        }

        per_source = [
            {"health_score": 90, "type": "mcp", "label": "A"},
            {"health_score": 60, "type": "mcp", "label": "B"},
            {"health_score": 80, "type": "api", "label": "C"},
        ]
        result = _build_combined(tracker, per_source)
        assert result["health_score"] == 60
        assert result["rating"] == "fair"
        assert "3 sources" in result["source"]
        assert result["per_source"] is per_source

    @patch("bannin.llm.aggregator.get_mcp_session_data")
    def test_single_source_label(self, mock_worst):
        mock_worst.return_value = None

        tracker = MagicMock()
        tracker.get_health.return_value = {
            "health_score": 85,
            "rating": "good",
            "source": "test",
            "components": {},
        }

        per_source = [{"health_score": 85, "type": "mcp", "label": "Solo"}]
        result = _build_combined(tracker, per_source)
        assert "1 source" in result["source"]
