"""Tests for conversation health scoring.

Validates calculate_health_score with known inputs against expected score
ranges and ratings. Tests component scoring, weight redistribution,
and edge cases.
"""

import pytest
from bannin.llm.health import (
    calculate_health_score,
    _score_context_freshness,
    _score_latency,
    _score_cost_efficiency,
    _score_vram_pressure,
    _score_inference_throughput,
    _get_rating,
)


# --- Context freshness scoring ---

class TestContextFreshness:
    def test_zero_usage(self):
        assert _score_context_freshness(0) == 100.0

    def test_low_usage(self):
        score = _score_context_freshness(20)
        assert score == 100.0

    def test_moderate_usage(self):
        score = _score_context_freshness(50)
        assert 90 < score <= 100  # 50% is just past safe zone (dz=80, safe=48%)

    def test_high_usage(self):
        score = _score_context_freshness(80)
        assert score <= 50

    def test_near_full(self):
        score = _score_context_freshness(95)
        assert score <= 5

    def test_full(self):
        score = _score_context_freshness(100)
        assert score == 0.0

    def test_danger_zone_affects_scoring(self):
        """Model with 65% danger zone should score worse at 70% than default."""
        with_dz = _score_context_freshness(70, danger_zone=65)
        without_dz = _score_context_freshness(70, danger_zone=80)
        assert with_dz < without_dz

    def test_below_danger_zone_safe(self):
        """Usage below 60% of danger zone should be 100."""
        score = _score_context_freshness(30, danger_zone=65)
        assert score == 100.0


# --- Latency scoring ---

class TestLatencyScoring:
    def test_no_data(self):
        score, detail = _score_latency(None)
        assert score == 100.0
        assert "Not enough" in detail

    def test_stable(self):
        score, _ = _score_latency(1.0)
        assert score == 100.0

    def test_improving(self):
        score, _ = _score_latency(0.8)
        assert score == 100.0

    def test_slight_increase(self):
        score, _ = _score_latency(1.3)
        assert 60 < score < 100

    def test_doubled(self):
        score, _ = _score_latency(2.0)
        assert score <= 25

    def test_severe(self):
        score, _ = _score_latency(3.0)
        assert score <= 5

    def test_extreme(self):
        score, _ = _score_latency(5.0)
        assert score == 0.0


# --- Cost efficiency scoring ---

class TestCostEfficiency:
    def test_no_data(self):
        score, _ = _score_cost_efficiency(None)
        assert score == 100.0

    def test_stable(self):
        score, _ = _score_cost_efficiency(1.0)
        assert score == 100.0

    def test_increasing(self):
        score, _ = _score_cost_efficiency(1.5)
        assert 55 < score < 65

    def test_doubled(self):
        score, _ = _score_cost_efficiency(2.0)
        assert 15 < score < 25


# --- VRAM pressure scoring ---

class TestVRAMPressure:
    def test_no_data(self):
        assert _score_vram_pressure(None) == 100.0

    def test_low_usage(self):
        assert _score_vram_pressure(30) == 100.0

    def test_half(self):
        assert _score_vram_pressure(50) == 100.0

    def test_moderate(self):
        score = _score_vram_pressure(70)
        assert 70 < score < 80

    def test_high(self):
        score = _score_vram_pressure(85)
        assert 20 < score < 50

    def test_critical(self):
        score = _score_vram_pressure(95)
        assert score < 20

    def test_full(self):
        score = _score_vram_pressure(100)
        assert score == 0.0


# --- Inference throughput scoring ---

class TestInferenceThroughput:
    def test_no_data(self):
        score, _ = _score_inference_throughput(None)
        assert score == 100.0

    def test_improving(self):
        score, _ = _score_inference_throughput(1.2)
        assert score == 100.0

    def test_slight_decrease(self):
        score, _ = _score_inference_throughput(0.85)
        assert 60 < score < 90

    def test_significant_decrease(self):
        score, _ = _score_inference_throughput(0.6)
        assert 20 < score < 50

    def test_critical(self):
        score, _ = _score_inference_throughput(0.3)
        assert score == 0.0


# --- Rating thresholds ---

class TestRating:
    thresholds = {"excellent": 90, "good": 70, "fair": 50, "poor": 30}

    def test_excellent(self):
        assert _get_rating(95, self.thresholds) == "excellent"

    def test_good(self):
        assert _get_rating(75, self.thresholds) == "good"

    def test_fair(self):
        assert _get_rating(55, self.thresholds) == "fair"

    def test_poor(self):
        assert _get_rating(35, self.thresholds) == "poor"

    def test_critical(self):
        assert _get_rating(10, self.thresholds) == "critical"

    def test_boundary_excellent(self):
        assert _get_rating(90, self.thresholds) == "excellent"

    def test_boundary_good(self):
        assert _get_rating(70, self.thresholds) == "good"


# --- Full health score calculation ---

class TestCalculateHealthScore:
    def test_fresh_conversation_no_signals(self):
        """Zero context, no other signals -> excellent."""
        result = calculate_health_score(
            context_percent=0,
            latency_ratio=None,
            cost_efficiency_trend=None,
        )
        assert result["health_score"] == 100.0
        assert result["rating"] == "excellent"
        assert result["recommendation"] is None

    def test_moderate_context_no_signals(self):
        """50% context with no other signals -> still high (below danger zone)."""
        result = calculate_health_score(
            context_percent=50,
            latency_ratio=None,
            cost_efficiency_trend=None,
        )
        assert result["health_score"] > 80
        assert result["rating"] in ("excellent", "good")

    def test_high_context_triggers_recommendation(self):
        """80%+ context should trigger a recommendation."""
        result = calculate_health_score(
            context_percent=85,
            latency_ratio=None,
            cost_efficiency_trend=None,
        )
        assert result["health_score"] < 50
        assert result["recommendation"] is not None

    def test_mcp_session_fatigue(self):
        """High session fatigue should lower score."""
        fresh = calculate_health_score(
            context_percent=20,
            latency_ratio=None,
            cost_efficiency_trend=None,
            session_fatigue={"session_fatigue": 10, "tool_call_burden": 5},
        )
        fatigued = calculate_health_score(
            context_percent=20,
            latency_ratio=None,
            cost_efficiency_trend=None,
            session_fatigue={"session_fatigue": 80, "tool_call_burden": 70},
        )
        assert fatigued["health_score"] < fresh["health_score"]

    def test_vram_pressure_affects_score(self):
        """High VRAM pressure should lower score."""
        low_vram = calculate_health_score(
            context_percent=20,
            latency_ratio=None,
            cost_efficiency_trend=None,
            vram_pressure=30,
        )
        high_vram = calculate_health_score(
            context_percent=20,
            latency_ratio=None,
            cost_efficiency_trend=None,
            vram_pressure=95,
        )
        assert high_vram["health_score"] < low_vram["health_score"]

    def test_api_mode_with_cost(self):
        """API mode: context + latency + cost should all factor in."""
        result = calculate_health_score(
            context_percent=40,
            latency_ratio=1.5,
            cost_efficiency_trend=1.3,
        )
        assert "cost_efficiency" in result["components"]
        assert "latency_health" in result["components"]
        assert result["rating"] in ("good", "fair", "excellent")

    def test_components_only_include_active_signals(self):
        """Only signals with weight > 0 should appear in components."""
        result = calculate_health_score(
            context_percent=30,
            latency_ratio=None,
            cost_efficiency_trend=None,
        )
        for comp in result["components"].values():
            assert comp["weight"] > 0

    def test_source_label_no_signals(self):
        """No session/vram/cost -> baseline source label."""
        result = calculate_health_score(
            context_percent=10,
            latency_ratio=None,
            cost_efficiency_trend=None,
        )
        assert "baseline" in result["source"].lower() or "No active" in result["source"]

    def test_source_label_mcp(self):
        """With session_fatigue -> includes MCP in source."""
        result = calculate_health_score(
            context_percent=10,
            latency_ratio=None,
            cost_efficiency_trend=None,
            session_fatigue={"session_fatigue": 20, "tool_call_burden": 10},
        )
        assert "MCP" in result["source"]

    def test_source_label_ollama(self):
        """With vram_pressure -> includes Ollama in source."""
        result = calculate_health_score(
            context_percent=10,
            latency_ratio=None,
            cost_efficiency_trend=None,
            vram_pressure=40,
        )
        assert "Ollama" in result["source"]

    def test_client_label_propagates(self):
        """client_label should appear in source string."""
        result = calculate_health_score(
            context_percent=10,
            latency_ratio=None,
            cost_efficiency_trend=None,
            session_fatigue={"session_fatigue": 20, "tool_call_burden": 10},
            client_label="Cursor",
        )
        assert "Cursor" in result["source"]

    def test_danger_zone_included_for_model(self):
        """When model is known, danger_zone should be in result."""
        result = calculate_health_score(
            context_percent=70,
            latency_ratio=None,
            cost_efficiency_trend=None,
            model="gpt-4o",
        )
        assert "danger_zone" in result

    def test_score_clamped_0_100(self):
        """Score should never exceed 0-100 range."""
        result = calculate_health_score(
            context_percent=200,
            latency_ratio=10.0,
            cost_efficiency_trend=5.0,
            session_fatigue={"session_fatigue": 100, "tool_call_burden": 100},
            vram_pressure=100,
        )
        assert 0 <= result["health_score"] <= 100

    def test_custom_weights(self):
        """Custom weights should override default profile."""
        result = calculate_health_score(
            context_percent=50,
            latency_ratio=1.5,
            cost_efficiency_trend=None,
            weights={"context_freshness": 0.5, "latency_health": 0.5},
        )
        assert "context_freshness" in result["components"]
        assert "latency_health" in result["components"]
        assert result["components"]["context_freshness"]["weight"] == 0.5

    def test_custom_thresholds(self):
        """Custom thresholds should change rating boundaries."""
        result = calculate_health_score(
            context_percent=0,
            latency_ratio=None,
            cost_efficiency_trend=None,
            thresholds={"excellent": 99, "good": 98, "fair": 97, "poor": 96},
        )
        assert result["health_score"] == 100.0
        assert result["rating"] == "excellent"
