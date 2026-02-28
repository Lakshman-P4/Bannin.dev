"""Tests for chatbot handler functions.

Validates that each handler returns well-formed responses with the correct
structure, handles edge cases, and degrades gracefully on errors.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from bannin.intelligence.chat import (
    chat,
    _handle_unsupported,
    _handle_memory,
    _handle_cpu,
    _handle_disk,
    _handle_process,
    _handle_health,
    _handle_history,
    _handle_ollama,
    _handle_llm_health,
    _handle_fallback,
    _format_size,
    _cached_scan,
    _disk_scan_cache,
    _disk_scan_lock,
)


# ---------------------------------------------------------------------------
# Response structure helpers
# ---------------------------------------------------------------------------

def _assert_valid_response(result: dict, expected_intent: str) -> None:
    """Every handler must return intent, response, data."""
    assert isinstance(result, dict)
    assert result["intent"] == expected_intent
    assert isinstance(result["response"], str)
    assert len(result["response"]) > 0
    assert isinstance(result["data"], dict)


# ---------------------------------------------------------------------------
# chat() top-level
# ---------------------------------------------------------------------------

class TestChatEntryPoint:
    def test_empty_message(self):
        result = chat("")
        assert result["intent"] == "empty"
        assert isinstance(result["response"], str)

    def test_whitespace_only(self):
        result = chat("   ")
        assert result["intent"] == "empty"

    def test_long_message_truncated(self):
        """Messages over 2000 chars should not crash."""
        result = chat("a" * 5000)
        _assert_valid_response(result, "general")

    def test_routes_to_correct_handler(self):
        """Verify that chat() dispatches to the right intent."""
        result = chat("how much ram do I have")
        assert result["intent"] == "memory"


# ---------------------------------------------------------------------------
# Unsupported handler
# ---------------------------------------------------------------------------

class TestHandleUnsupported:
    def test_battery_specific_message(self):
        result = _handle_unsupported("check my battery")
        _assert_valid_response(result, "unsupported")
        assert "battery" in result["response"].lower()

    def test_wifi_specific_message(self):
        result = _handle_unsupported("how's my wifi")
        _assert_valid_response(result, "unsupported")
        assert "WiFi" in result["response"]

    def test_generic_unsupported(self):
        result = _handle_unsupported("launch my spaceship")
        _assert_valid_response(result, "unsupported")
        assert "outside" in result["response"].lower() or "can do" in result["response"].lower()

    def test_suggestions_present(self):
        result = _handle_unsupported("set a timer")
        assert "Disk" in result["response"]
        assert "Memory" in result["response"]
        assert "CPU" in result["response"]


# ---------------------------------------------------------------------------
# Fallback handler
# ---------------------------------------------------------------------------

class TestHandleFallback:
    def test_returns_guidance(self):
        result = _handle_fallback("random gibberish")
        _assert_valid_response(result, "general")
        assert "disk" in result["response"].lower() or "memory" in result["response"].lower()


# ---------------------------------------------------------------------------
# Memory handler
# ---------------------------------------------------------------------------

_MOCK_MEMORY = {
    "total_gb": 16.0,
    "available_gb": 4.2,
    "used_gb": 11.8,
    "percent": 73.8,
}

_MOCK_BREAKDOWN = {
    "cpu": [],
    "ram": [
        {"name": "Google Chrome", "display": "1.2 GB", "memory_mb": 1200},
        {"name": "VS Code", "display": "800 MB", "memory_mb": 800},
    ],
}


class TestHandleMemory:
    @patch("bannin.intelligence.chat.get_resource_breakdown", return_value=_MOCK_BREAKDOWN)
    @patch("bannin.intelligence.chat.get_memory_metrics", return_value=_MOCK_MEMORY)
    def test_basic_response(self, mock_mem, mock_bk):
        result = _handle_memory("how much ram")
        _assert_valid_response(result, "memory")
        assert "73" in result["response"] or "74" in result["response"]
        assert "data" in result
        assert result["data"]["memory"]["percent"] == 73.8

    @patch("bannin.intelligence.chat.get_resource_breakdown", return_value=_MOCK_BREAKDOWN)
    @patch("bannin.intelligence.chat.get_memory_metrics", return_value=_MOCK_MEMORY)
    def test_top_consumers_listed(self, mock_mem, mock_bk):
        result = _handle_memory("memory usage")
        assert "Google Chrome" in result["response"]
        assert "VS Code" in result["response"]

    @patch("bannin.intelligence.chat.get_resource_breakdown", return_value=_MOCK_BREAKDOWN)
    @patch("bannin.intelligence.chat.get_memory_metrics", return_value={
        "total_gb": 8.0, "available_gb": 0.5, "used_gb": 7.5, "percent": 94.0,
    })
    def test_high_pressure_advice(self, mock_mem, mock_bk):
        result = _handle_memory("memory")
        assert "pressure" in result["response"].lower()

    @patch("bannin.intelligence.chat.get_resource_breakdown", return_value={"cpu": [], "ram": []})
    @patch("bannin.intelligence.chat.get_memory_metrics", return_value={
        "total_gb": 8.0, "available_gb": 6.0, "used_gb": 2.0, "percent": 25.0,
    })
    def test_low_usage_healthy(self, mock_mem, mock_bk):
        result = _handle_memory("ram")
        assert "healthy" in result["response"].lower()

    @patch("bannin.intelligence.chat.get_resource_breakdown", return_value=_MOCK_BREAKDOWN)
    @patch("bannin.intelligence.chat.get_memory_metrics", return_value={
        "total_gb": 7.5, "available_gb": 1.0, "used_gb": 6.5, "percent": 87.0,
    })
    def test_low_ram_machine_upgrade_hint(self, mock_mem, mock_bk):
        """Machines with <= 8 GB should get an upgrade suggestion."""
        result = _handle_memory("memory")
        assert "upgrade" in result["response"].lower() or "8 GB" in result["response"] or "8" in result["response"]

    @patch("bannin.intelligence.chat.get_memory_metrics", side_effect=Exception("psutil failed"))
    def test_graceful_failure(self, mock_mem):
        result = _handle_memory("memory")
        _assert_valid_response(result, "memory")
        assert "couldn't" in result["response"].lower() or "try again" in result["response"].lower()


# ---------------------------------------------------------------------------
# CPU handler
# ---------------------------------------------------------------------------

_MOCK_CPU = {
    "percent": 85.0,
    "per_core": [90.0, 80.0, 95.0, 70.0],
    "count_physical": 4,
    "count_logical": 4,
    "frequency_mhz": 3200,
}

_MOCK_CPU_BREAKDOWN = {
    "cpu": [
        {"name": "Python", "display": "45% CPU", "cpu_percent": 45.0},
        {"name": "Google Chrome", "display": "20% CPU", "cpu_percent": 20.0},
    ],
    "ram": [],
}


class TestHandleCpu:
    @patch("bannin.intelligence.chat.get_resource_breakdown", return_value=_MOCK_CPU_BREAKDOWN)
    @patch("bannin.intelligence.chat.get_cpu_metrics", return_value=_MOCK_CPU)
    def test_basic_response(self, mock_cpu, mock_bk):
        result = _handle_cpu("cpu usage")
        _assert_valid_response(result, "cpu")
        assert "85" in result["response"]
        assert result["data"]["cpu"]["percent"] == 85.0

    @patch("bannin.intelligence.chat.get_resource_breakdown", return_value=_MOCK_CPU_BREAKDOWN)
    @patch("bannin.intelligence.chat.get_cpu_metrics", return_value=_MOCK_CPU)
    def test_hot_cores_detected(self, mock_cpu, mock_bk):
        result = _handle_cpu("cpu")
        assert "Core" in result["response"]

    @patch("bannin.intelligence.chat.get_resource_breakdown", return_value=_MOCK_CPU_BREAKDOWN)
    @patch("bannin.intelligence.chat.get_cpu_metrics", return_value=_MOCK_CPU)
    def test_top_consumer_listed(self, mock_cpu, mock_bk):
        result = _handle_cpu("processor load")
        assert "Python" in result["response"]

    @patch("bannin.intelligence.chat.get_resource_breakdown", return_value={"cpu": [], "ram": []})
    @patch("bannin.intelligence.chat.get_cpu_metrics", return_value={
        "percent": 12.0, "per_core": [10.0, 14.0], "count_physical": 2, "count_logical": 2, "frequency_mhz": 2800,
    })
    def test_low_usage_relaxed(self, mock_cpu, mock_bk):
        result = _handle_cpu("cpu")
        assert "relaxed" in result["response"].lower()

    @patch("bannin.intelligence.chat.get_cpu_metrics", side_effect=Exception("psutil error"))
    def test_graceful_failure(self, mock_cpu):
        result = _handle_cpu("cpu")
        _assert_valid_response(result, "cpu")
        assert "couldn't" in result["response"].lower()


# ---------------------------------------------------------------------------
# Disk handler
# ---------------------------------------------------------------------------

_MOCK_DISK = {
    "total_gb": 500.0,
    "used_gb": 350.0,
    "free_gb": 150.0,
    "percent": 70.0,
}


class TestHandleDisk:
    @patch("bannin.intelligence.chat._cached_scan", return_value=[])
    @patch("bannin.intelligence.chat.get_disk_metrics", return_value=_MOCK_DISK)
    def test_basic_response(self, mock_disk, mock_scan):
        result = _handle_disk("disk usage")
        _assert_valid_response(result, "disk")
        assert "70" in result["response"]
        assert result["data"]["disk"]["free_gb"] == 150.0

    @patch("bannin.intelligence.chat._cached_scan")
    @patch("bannin.intelligence.chat.get_disk_metrics", return_value=_MOCK_DISK)
    def test_cleanup_suggestions(self, mock_disk, mock_scan):
        mock_scan.side_effect = lambda name, fn: (
            [{"name": "Downloads", "path": "/home/user/Downloads", "size_gb": 5.2}] if name == "user_dirs"
            else [{"name": "npm cache", "path": "/home/.npm", "size_gb": 1.1}]
        )
        result = _handle_disk("clean up disk")
        assert "Downloads" in result["response"]
        assert "npm" in result["response"].lower()

    @patch("bannin.intelligence.chat._cached_scan", return_value=[])
    @patch("bannin.intelligence.chat.get_disk_metrics", return_value={
        "total_gb": 256.0, "used_gb": 240.0, "free_gb": 16.0, "percent": 93.0,
    })
    def test_critical_disk_advice(self, mock_disk, mock_scan):
        result = _handle_disk("disk")
        assert "critically" in result["response"].lower() or "critical" in result["response"].lower()

    @patch("bannin.intelligence.chat.get_disk_metrics", side_effect=Exception("disk read failed"))
    def test_graceful_failure(self, mock_disk):
        result = _handle_disk("disk")
        _assert_valid_response(result, "disk")
        assert "couldn't" in result["response"].lower()


# ---------------------------------------------------------------------------
# Process handler
# ---------------------------------------------------------------------------

class TestHandleProcess:
    @patch("bannin.intelligence.chat.get_grouped_processes", return_value=[
        {"name": "Google Chrome", "cpu_percent": 15.0, "memory_mb": 1200, "instance_count": 26},
        {"name": "VS Code", "cpu_percent": 8.0, "memory_mb": 600, "instance_count": 1},
    ])
    def test_basic_response(self, mock_procs):
        result = _handle_process("what's running")
        _assert_valid_response(result, "process")
        assert "Google Chrome" in result["response"]
        assert "26 instances" in result["response"]

    @patch("bannin.intelligence.chat.get_grouped_processes", return_value=[])
    def test_empty_process_list(self, mock_procs):
        result = _handle_process("top apps")
        _assert_valid_response(result, "process")


# ---------------------------------------------------------------------------
# Health handler
# ---------------------------------------------------------------------------

_MOCK_SUMMARY = {
    "headline": "System is running smoothly",
    "details": "CPU 23%, RAM 45%, Disk 60%.",
    "suggestions": ["Close unused browser tabs", "Clear temp files"],
}


class TestHandleHealth:
    @patch("bannin.intelligence.summary.generate_summary", return_value=_MOCK_SUMMARY)
    def test_basic_response(self, mock_summary):
        result = _handle_health("system health")
        _assert_valid_response(result, "health")
        assert "smoothly" in result["response"]
        assert "browser tabs" in result["response"]

    @patch("bannin.intelligence.summary.generate_summary", return_value={
        "headline": "OK", "details": None, "suggestions": None,
    })
    def test_minimal_summary(self, mock_summary):
        result = _handle_health("health check")
        _assert_valid_response(result, "health")
        assert "OK" in result["response"]


# ---------------------------------------------------------------------------
# History handler
# ---------------------------------------------------------------------------

class TestHandleHistory:
    @patch("bannin.analytics.store.AnalyticsStore")
    def test_no_events(self, mock_store_cls):
        mock_store = MagicMock()
        mock_store.get_stats.return_value = {"total_events": 0}
        mock_store_cls.get.return_value = mock_store
        result = _handle_history("what happened")
        _assert_valid_response(result, "history")
        assert "don't have" in result["response"].lower() or "no" in result["response"].lower()

    @patch("bannin.analytics.store.AnalyticsStore")
    def test_with_events(self, mock_store_cls):
        mock_store = MagicMock()
        mock_store.get_stats.return_value = {
            "total_events": 42,
            "by_type": {"alert": 10, "metric_snapshot": 30, "session_start": 2},
        }
        mock_store.query.side_effect = lambda event_type, limit: (
            [{"severity": "warning", "message": "RAM at 92%", "timestamp": "2026-02-24T10:00:00"}]
            if event_type == "alert" else []
        )
        mock_store_cls.get.return_value = mock_store
        result = _handle_history("what happened while I was away")
        _assert_valid_response(result, "history")
        assert "42" in result["response"]
        assert "RAM" in result["response"]

    @patch("bannin.analytics.store.AnalyticsStore")
    def test_store_unavailable(self, mock_store_cls):
        mock_store_cls.get.side_effect = Exception("store not initialized")
        result = _handle_history("history")
        _assert_valid_response(result, "history")
        assert "couldn't" in result["response"].lower()


# ---------------------------------------------------------------------------
# Ollama handler
# ---------------------------------------------------------------------------

class TestHandleOllama:
    @patch("bannin.llm.ollama.OllamaMonitor")
    def test_not_running(self, mock_cls):
        mock = MagicMock()
        mock.get_health.return_value = {"available": False}
        mock_cls.get.return_value = mock
        result = _handle_ollama("ollama status")
        _assert_valid_response(result, "ollama")
        assert "not" in result["response"].lower() or "doesn't" in result["response"].lower()

    @patch("bannin.llm.ollama.OllamaMonitor")
    def test_running_no_models(self, mock_cls):
        mock = MagicMock()
        mock.get_health.return_value = {"available": True, "models": []}
        mock_cls.get.return_value = mock
        result = _handle_ollama("ollama")
        _assert_valid_response(result, "ollama")
        assert "no models" in result["response"].lower()

    @patch("bannin.llm.ollama.OllamaMonitor")
    def test_running_with_models(self, mock_cls):
        mock = MagicMock()
        mock.get_health.return_value = {
            "available": True,
            "models": [{
                "name": "llama3.1:8b",
                "parameter_size": "8B",
                "quantization": "Q4_0",
                "vram_gb": 4.5,
                "vram_percent": 28.0,
                "expires_at": "2026-02-24T12:00:00",
            }],
            "vram_pressure": 28.0,
        }
        mock_cls.get.return_value = mock
        result = _handle_ollama("what model is loaded")
        _assert_valid_response(result, "ollama")
        assert "llama3.1:8b" in result["response"]
        assert "4.5" in result["response"]

    @patch("bannin.llm.ollama.OllamaMonitor")
    def test_high_vram_pressure(self, mock_cls):
        mock = MagicMock()
        mock.get_health.return_value = {
            "available": True,
            "models": [{"name": "mixtral", "parameter_size": "46B", "quantization": "Q4_K_M", "vram_gb": 12.0, "vram_percent": 85.0}],
            "vram_pressure": 85.0,
        }
        mock_cls.get.return_value = mock
        result = _handle_ollama("ollama")
        assert "high" in result["response"].lower()

    @patch("bannin.llm.ollama.OllamaMonitor")
    def test_import_failure(self, mock_cls):
        mock_cls.get.side_effect = Exception("import failed")
        result = _handle_ollama("ollama")
        _assert_valid_response(result, "ollama")
        assert "couldn't" in result["response"].lower()


# ---------------------------------------------------------------------------
# LLM health handler
# ---------------------------------------------------------------------------

class TestHandleLlmHealth:
    @patch("bannin.llm.aggregator.compute_health")
    def test_healthy_conversation(self, mock_health):
        mock_health.return_value = {
            "health_score": 92,
            "rating": "excellent",
            "source": "MCP Session",
            "components": {
                "context_freshness": {"score": 95, "detail": "15% of context used"},
                "session_duration": {"score": 90, "detail": "12 minutes"},
            },
            "recommendation": None,
            "danger_zone": None,
            "per_source": [],
        }
        result = _handle_llm_health("conversation health")
        _assert_valid_response(result, "llm_health")
        assert "92" in result["response"]
        assert "excellent" in result["response"]

    @patch("bannin.llm.aggregator.compute_health")
    def test_degraded_conversation(self, mock_health):
        mock_health.return_value = {
            "health_score": 35,
            "rating": "poor",
            "source": "API Tracker",
            "components": {
                "context_freshness": {"score": 20, "detail": "85% of context used"},
            },
            "recommendation": "Start a new conversation",
            "danger_zone": {"in_danger_zone": True, "danger_zone_percent": 80, "model": "claude-3.5-sonnet"},
            "per_source": [],
        }
        result = _handle_llm_health("how's my conversation")
        _assert_valid_response(result, "llm_health")
        assert "35" in result["response"]
        assert "poor" in result["response"]
        assert "Start a new conversation" in result["response"]
        assert "danger zone" in result["response"].lower()

    @patch("bannin.llm.aggregator.compute_health")
    def test_multi_source(self, mock_health):
        mock_health.return_value = {
            "health_score": 60,
            "rating": "fair",
            "per_source": [
                {"label": "MCP Session", "health_score": 60, "rating": "fair", "components": {}, "recommendation": None},
                {"label": "Ollama", "health_score": 80, "rating": "good", "components": {}, "recommendation": None},
            ],
            "recommendation": None,
            "danger_zone": None,
        }
        result = _handle_llm_health("llm health")
        _assert_valid_response(result, "llm_health")
        assert "2 active sources" in result["response"]
        assert "MCP Session" in result["response"]
        assert "Ollama" in result["response"]

    @patch("bannin.llm.aggregator.compute_health", side_effect=Exception("health module not init"))
    def test_graceful_failure(self, mock_health):
        result = _handle_llm_health("conversation health")
        _assert_valid_response(result, "llm_health")
        assert "couldn't" in result["response"].lower()


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

class TestFormatSize:
    def test_gb_range(self):
        assert _format_size(2.5) == "2.5 GB"

    def test_mb_range(self):
        assert _format_size(0.5) == "512 MB"

    def test_small_mb(self):
        assert _format_size(0.01) == "10 MB"

    def test_exact_gb(self):
        assert _format_size(1.0) == "1.0 GB"


class TestCachedScan:
    def setup_method(self):
        with _disk_scan_lock:
            _disk_scan_cache.clear()

    def test_returns_scan_result(self):
        result = _cached_scan("test_key", lambda: [{"name": "a"}])
        assert result == [{"name": "a"}]

    def test_uses_cache_on_second_call(self):
        call_count = 0

        def scanner():
            nonlocal call_count
            call_count += 1
            return [{"name": "data"}]

        _cached_scan("test_cache", scanner)
        _cached_scan("test_cache", scanner)
        assert call_count == 1

    def test_cache_bounded(self):
        """Cache should evict when exceeding 10 entries."""
        for i in range(12):
            _cached_scan(f"key_{i}", lambda: [])
        with _disk_scan_lock:
            assert len(_disk_scan_cache) <= 11
