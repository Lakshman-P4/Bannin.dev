"""Tests for L2 recommendation engine.

Validates that each of the 12 recommendation rules fires on expected
input and produces well-formed recommendation dicts.
"""

from __future__ import annotations

import pytest

from bannin.intelligence.recommendations import generate_recommendations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_snapshot() -> dict:
    """Baseline snapshot that triggers no recommendations."""
    return {
        "cpu": {"percent": 20.0},
        "memory": {"percent": 40.0, "total_gb": 16.0, "used_gb": 6.4, "available_gb": 9.6},
        "disk": {"percent": 50.0, "free_gb": 100.0, "total_gb": 200.0, "used_gb": 100.0},
        "predictions": {"oom": {"ram": {"confidence": 0, "minutes_until_full": 999}}},
        "platform": {},
        "health": {"health_score": 95, "rating": "excellent", "components": {}, "danger_zone": None},
        "mcp": {},
        "ollama": {},
        "llm": {"total_cost_usd": 0.0},
        "top_processes": [],
    }


def _find_rec(recs: list[dict], category: str, substring: str) -> dict | None:
    """Find a recommendation by category and message substring."""
    for r in recs:
        if r["category"] == category and substring.lower() in r["message"].lower():
            return r
    return None


def _assert_rec_shape(rec: dict) -> None:
    """Every recommendation must have the required fields."""
    assert "id" in rec
    assert rec["id"].startswith("rec_")
    assert isinstance(rec["priority"], int)
    assert 1 <= rec["priority"] <= 5
    assert isinstance(rec["category"], str)
    assert isinstance(rec["message"], str)
    assert len(rec["message"]) > 0
    assert isinstance(rec["action"], str)
    assert len(rec["action"]) > 0
    assert isinstance(rec["confidence"], float)
    assert 0.0 <= rec["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Rule 1: OOM imminent
# ---------------------------------------------------------------------------

class TestOOMImminent:
    def test_triggers_on_high_confidence_low_time(self):
        snap = _empty_snapshot()
        snap["predictions"]["oom"]["ram"] = {"confidence": 85, "minutes_until_full": 5}
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "system", "OOM")
        assert rec is not None
        _assert_rec_shape(rec)
        assert rec["priority"] == 1

    def test_does_not_trigger_low_confidence(self):
        snap = _empty_snapshot()
        snap["predictions"]["oom"]["ram"] = {"confidence": 40, "minutes_until_full": 5}
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "system", "OOM") is None

    def test_does_not_trigger_distant_oom(self):
        snap = _empty_snapshot()
        snap["predictions"]["oom"]["ram"] = {"confidence": 90, "minutes_until_full": 30}
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "system", "OOM") is None


# ---------------------------------------------------------------------------
# Rule 2: Session expiring
# ---------------------------------------------------------------------------

class TestSessionExpiring:
    def test_triggers_under_15_minutes(self):
        snap = _empty_snapshot()
        snap["platform"] = {"session": {"remaining_seconds": 600}}
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "platform", "expires")
        assert rec is not None
        _assert_rec_shape(rec)
        assert rec["priority"] == 1

    def test_does_not_trigger_long_session(self):
        snap = _empty_snapshot()
        snap["platform"] = {"session": {"remaining_seconds": 3600}}
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "platform", "expires") is None


# ---------------------------------------------------------------------------
# Rule 3: Conversation health degraded
# ---------------------------------------------------------------------------

class TestConversationDegraded:
    def test_triggers_on_low_health(self):
        snap = _empty_snapshot()
        snap["health"] = {
            "health_score": 30, "rating": "poor",
            "recommendation": "Start a new conversation",
            "components": {}, "danger_zone": None,
        }
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "llm", "health")
        assert rec is not None
        _assert_rec_shape(rec)
        assert rec["priority"] == 2

    def test_does_not_trigger_healthy(self):
        snap = _empty_snapshot()
        snap["health"]["health_score"] = 80
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "llm", "health is") is None


# ---------------------------------------------------------------------------
# Rule 4: Context window danger zone
# ---------------------------------------------------------------------------

class TestContextDangerZone:
    def test_triggers_in_danger_zone(self):
        snap = _empty_snapshot()
        snap["health"] = {
            "health_score": 50, "rating": "fair",
            "components": {"context_freshness": {"score": 20, "detail": "85% used"}},
            "danger_zone": {"in_danger_zone": True, "danger_zone_percent": 80, "model": "gpt-4"},
        }
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "llm", "danger zone")
        assert rec is not None
        _assert_rec_shape(rec)
        assert "gpt-4" in rec["message"]

    def test_does_not_trigger_outside_danger(self):
        snap = _empty_snapshot()
        snap["health"]["danger_zone"] = None
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "llm", "danger zone") is None


# ---------------------------------------------------------------------------
# Rule 5: MCP session fatigue
# ---------------------------------------------------------------------------

class TestMCPFatigue:
    def test_triggers_high_fatigue(self):
        snap = _empty_snapshot()
        snap["mcp"] = {"session_fatigue": 75, "total_tool_calls": 120}
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "llm", "fatigue")
        assert rec is not None
        _assert_rec_shape(rec)
        assert rec["priority"] == 3

    def test_does_not_trigger_low_fatigue(self):
        snap = _empty_snapshot()
        snap["mcp"] = {"session_fatigue": 30, "total_tool_calls": 10}
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "llm", "fatigue") is None


# ---------------------------------------------------------------------------
# Rule 6: RAM pressure with cause
# ---------------------------------------------------------------------------

class TestRAMPressure:
    def test_triggers_with_culprit(self):
        snap = _empty_snapshot()
        snap["memory"]["percent"] = 88.0
        snap["top_processes"] = [{"name": "Chrome", "memory_mb": 1500}]
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "system", "RAM")
        assert rec is not None
        _assert_rec_shape(rec)
        assert "Chrome" in rec["message"]

    def test_triggers_without_large_process(self):
        snap = _empty_snapshot()
        snap["memory"]["percent"] = 85.0
        snap["top_processes"] = [{"name": "tiny", "memory_mb": 50}]
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "system", "RAM")
        assert rec is not None
        assert "tiny" not in rec["message"]

    def test_does_not_trigger_normal_ram(self):
        snap = _empty_snapshot()
        snap["memory"]["percent"] = 50.0
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "system", "RAM") is None


# ---------------------------------------------------------------------------
# Rule 7: Ollama VRAM pressure
# ---------------------------------------------------------------------------

class TestOllamaVRAM:
    def test_triggers_high_vram(self):
        snap = _empty_snapshot()
        snap["ollama"] = {
            "vram_pressure": 82.0,
            "models": [{"name": "llama3.1:70b"}],
        }
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "local_llm", "VRAM")
        assert rec is not None
        _assert_rec_shape(rec)
        assert "llama3.1:70b" in rec["message"]

    def test_does_not_trigger_low_vram(self):
        snap = _empty_snapshot()
        snap["ollama"] = {"vram_pressure": 30.0, "models": []}
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "local_llm", "VRAM") is None


# ---------------------------------------------------------------------------
# Rule 8: CPU saturated
# ---------------------------------------------------------------------------

class TestCPUSaturated:
    def test_triggers_high_cpu_with_process(self):
        snap = _empty_snapshot()
        snap["cpu"]["percent"] = 95.0
        snap["top_processes"] = [{"name": "python", "cpu_percent": 80.0}]
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "system", "CPU")
        assert rec is not None
        _assert_rec_shape(rec)
        assert "python" in rec["message"]

    def test_does_not_trigger_moderate_cpu(self):
        snap = _empty_snapshot()
        snap["cpu"]["percent"] = 60.0
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "system", "CPU") is None


# ---------------------------------------------------------------------------
# Rule 9: Disk critically low
# ---------------------------------------------------------------------------

class TestDiskCritical:
    def test_triggers_high_percent(self):
        snap = _empty_snapshot()
        snap["disk"] = {"percent": 95.0, "free_gb": 10.0}
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "system", "Disk")
        assert rec is not None
        _assert_rec_shape(rec)

    def test_triggers_low_free_gb(self):
        snap = _empty_snapshot()
        snap["disk"] = {"percent": 70.0, "free_gb": 3.0}
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "system", "Disk")
        assert rec is not None

    def test_does_not_trigger_healthy_disk(self):
        snap = _empty_snapshot()
        snap["disk"] = {"percent": 60.0, "free_gb": 80.0}
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "system", "Disk") is None


# ---------------------------------------------------------------------------
# Rule 10: LLM cost trending up
# ---------------------------------------------------------------------------

class TestLLMCost:
    def test_triggers_high_cost(self):
        snap = _empty_snapshot()
        snap["llm"] = {"total_cost_usd": 7.50}
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "llm", "spend")
        assert rec is not None
        _assert_rec_shape(rec)
        assert "$7.50" in rec["message"]

    def test_does_not_trigger_low_cost(self):
        snap = _empty_snapshot()
        snap["llm"] = {"total_cost_usd": 1.20}
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "llm", "spend") is None


# ---------------------------------------------------------------------------
# Rule 11: Latency degrading
# ---------------------------------------------------------------------------

class TestLatencyDegrading:
    def test_triggers_low_latency_score(self):
        snap = _empty_snapshot()
        snap["health"] = {
            "health_score": 60, "rating": "fair",
            "components": {"latency_health": {"score": 35, "detail": "3.2s avg"}},
            "danger_zone": None,
        }
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "llm", "latency")
        assert rec is not None
        _assert_rec_shape(rec)

    def test_does_not_trigger_good_latency(self):
        snap = _empty_snapshot()
        snap["health"]["components"] = {"latency_health": {"score": 90, "detail": "0.8s avg"}}
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "llm", "latency") is None


# ---------------------------------------------------------------------------
# Rule 12: Ollama model about to unload
# ---------------------------------------------------------------------------

class TestOllamaModelExpiry:
    def test_triggers_near_expiry(self):
        from datetime import datetime, timezone, timedelta
        near_future = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()
        snap = _empty_snapshot()
        snap["ollama"] = {
            "vram_pressure": 30.0,
            "models": [{"name": "codellama:13b", "expires_at": near_future}],
        }
        recs = generate_recommendations(snap)
        rec = _find_rec(recs, "local_llm", "expires")
        assert rec is not None
        _assert_rec_shape(rec)
        assert "codellama" in rec["message"]

    def test_does_not_trigger_distant_expiry(self):
        from datetime import datetime, timezone, timedelta
        far_future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        snap = _empty_snapshot()
        snap["ollama"] = {
            "vram_pressure": 30.0,
            "models": [{"name": "llama", "expires_at": far_future}],
        }
        recs = generate_recommendations(snap)
        assert _find_rec(recs, "local_llm", "expires") is None


# ---------------------------------------------------------------------------
# Output structure and sorting
# ---------------------------------------------------------------------------

class TestOutputStructure:
    def test_empty_snapshot_no_recs(self):
        recs = generate_recommendations(_empty_snapshot())
        assert isinstance(recs, list)
        assert len(recs) == 0

    def test_sorted_by_priority(self):
        snap = _empty_snapshot()
        snap["predictions"]["oom"]["ram"] = {"confidence": 90, "minutes_until_full": 3}
        snap["cpu"]["percent"] = 95.0
        snap["top_processes"] = [{"name": "python", "cpu_percent": 90.0}]
        snap["llm"] = {"total_cost_usd": 10.0}
        recs = generate_recommendations(snap)
        priorities = [r["priority"] for r in recs]
        assert priorities == sorted(priorities)

    def test_unique_ids(self):
        snap = _empty_snapshot()
        snap["memory"]["percent"] = 90.0
        snap["cpu"]["percent"] = 95.0
        snap["disk"] = {"percent": 95.0, "free_gb": 2.0}
        snap["top_processes"] = [{"name": "python", "cpu_percent": 90.0, "memory_mb": 500}]
        recs = generate_recommendations(snap)
        ids = [r["id"] for r in recs]
        assert len(ids) == len(set(ids))

    def test_multiple_rules_fire(self):
        """When everything is bad, multiple recommendations should fire."""
        snap = _empty_snapshot()
        snap["predictions"]["oom"]["ram"] = {"confidence": 90, "minutes_until_full": 3}
        snap["memory"]["percent"] = 92.0
        snap["cpu"]["percent"] = 96.0
        snap["disk"] = {"percent": 95.0, "free_gb": 2.0}
        snap["top_processes"] = [{"name": "python", "cpu_percent": 90.0, "memory_mb": 500}]
        recs = generate_recommendations(snap)
        assert len(recs) >= 3
