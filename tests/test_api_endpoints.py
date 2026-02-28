"""Smoke tests for all Bannin API endpoints.

Uses FastAPI TestClient to verify every endpoint returns the expected
status code and response shape. No live server needed.
"""

import pytest


# --- Core endpoints ---

class TestCoreEndpoints:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_status(self, client):
        r = client.get("/status")
        assert r.status_code == 200
        data = r.json()
        assert data["agent"] == "bannin"
        assert data["version"] == "0.1.0"
        assert "hostname" in data
        assert "platform" in data
        assert "uptime_seconds" in data

    def test_metrics(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data

    def test_dashboard(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "Bannin" in r.text

    def test_metrics_self(self, client):
        r = client.get("/metrics/self")
        assert r.status_code == 200
        data = r.json()
        assert "pid" in data
        assert isinstance(data["pid"], int)
        assert "cpu_percent" in data
        assert isinstance(data["cpu_percent"], (int, float))
        assert "memory_rss_mb" in data
        assert data["memory_rss_mb"] > 0
        assert "memory_vms_mb" in data
        assert "threads" in data
        assert isinstance(data["threads"], int)
        assert data["threads"] >= 1
        assert "uptime_seconds" in data
        assert "create_time" in data


# --- Process endpoints ---

class TestProcessEndpoints:
    def test_processes(self, client):
        r = client.get("/processes")
        assert r.status_code == 200
        data = r.json()
        assert "top_processes" in data
        assert "resource_breakdown" in data
        assert "summary" in data

    def test_processes_limit(self, client):
        r = client.get("/processes?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert len(data["top_processes"]) <= 5


# --- Intelligence endpoints ---

class TestIntelligenceEndpoints:
    def test_summary(self, client):
        r = client.get("/summary")
        assert r.status_code == 200
        data = r.json()
        assert "headline" in data
        assert "level" in data

    def test_alerts(self, client):
        r = client.get("/alerts")
        assert r.status_code == 200

    def test_alerts_active(self, client):
        r = client.get("/alerts/active")
        assert r.status_code == 200
        data = r.json()
        assert "active" in data

    def test_predictions_oom(self, client):
        r = client.get("/predictions/oom")
        assert r.status_code == 200

    def test_history_memory(self, client):
        r = client.get("/history/memory")
        assert r.status_code == 200
        data = r.json()
        assert "readings" in data
        assert "count" in data

    def test_history_memory_custom_period(self, client):
        r = client.get("/history/memory?minutes=2")
        assert r.status_code == 200
        assert r.json()["period_minutes"] == 2.0

    def test_tasks(self, client):
        r = client.get("/tasks")
        assert r.status_code == 200

    def test_recommendations(self, client):
        r = client.get("/recommendations")
        assert r.status_code == 200
        data = r.json()
        assert "recommendations" in data


# --- LLM endpoints ---

class TestLLMEndpoints:
    def test_llm_usage(self, client):
        r = client.get("/llm/usage")
        assert r.status_code == 200
        data = r.json()
        assert "total_calls" in data
        assert "total_cost_usd" in data

    def test_llm_calls(self, client):
        r = client.get("/llm/calls")
        assert r.status_code == 200
        data = r.json()
        assert "calls" in data

    def test_llm_context_requires_model(self, client):
        r = client.get("/llm/context")
        assert r.status_code == 400
        assert "error" in r.json()

    def test_llm_latency(self, client):
        r = client.get("/llm/latency")
        assert r.status_code == 200

    def test_llm_health(self, client):
        r = client.get("/llm/health")
        assert r.status_code == 200
        data = r.json()
        assert "health_score" in data
        assert "rating" in data

    def test_llm_connections(self, client):
        r = client.get("/llm/connections")
        assert r.status_code == 200
        data = r.json()
        assert "connections" in data


# --- MCP endpoints ---

class TestMCPEndpoints:
    def test_mcp_sessions_empty(self, client):
        r = client.get("/mcp/sessions")
        assert r.status_code == 200
        data = r.json()
        assert "sessions" in data
        assert "count" in data

    def test_mcp_session_push(self, client):
        payload = {
            "session_id": "test-session-001",
            "client_label": "Test Client",
            "session_fatigue": 25,
            "tool_call_burden": 10,
            "estimated_context_percent": 30,
            "session_duration_minutes": 5,
            "total_tool_calls": 12,
        }
        r = client.post("/mcp/session", json=payload)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_mcp_session_appears_after_push(self, client):
        payload = {
            "session_id": "test-session-002",
            "client_label": "Integration Test",
            "session_fatigue": 15,
            "tool_call_burden": 5,
        }
        client.post("/mcp/session", json=payload)
        r = client.get("/mcp/sessions")
        data = r.json()
        session_ids = [s.get("session_id") for s in data["sessions"]]
        assert "test-session-002" in session_ids


# --- Ollama endpoint ---

class TestOllamaEndpoint:
    def test_ollama_status(self, client):
        r = client.get("/ollama")
        assert r.status_code == 200
        data = r.json()
        assert "available" in data


# --- Analytics endpoints ---

# --- SSE stream endpoint ---

class TestSSEEndpoint:
    def test_stream_sse_helpers(self):
        """Verify SSE formatting helper produces valid SSE output."""
        from bannin.api import _sse_event
        event = _sse_event("metrics", {"cpu": 50.0})
        assert event.startswith("event: metrics\n")
        assert '"cpu": 50.0' in event
        assert event.endswith("\n\n")

    def test_stream_collector_functions(self):
        """Verify SSE data collectors return list of (type, dict) tuples."""
        from bannin.api import _collect_fast, _collect_medium, _collect_slow
        fast = _collect_fast()
        assert isinstance(fast, list)
        for event_type, data in fast:
            assert isinstance(event_type, str)
            assert isinstance(data, dict)

        medium = _collect_medium()
        assert isinstance(medium, list)

        slow = _collect_slow()
        assert isinstance(slow, list)
        event_types = {t for t, _ in slow}
        assert "status" in event_types


# --- Analytics endpoints ---

class TestAnalyticsEndpoints:
    def test_analytics_stats(self, client):
        r = client.get("/analytics/stats")
        assert r.status_code == 200

    def test_analytics_events(self, client):
        r = client.get("/analytics/events")
        assert r.status_code == 200
        data = r.json()
        assert "events" in data

    def test_analytics_search_requires_query(self, client):
        r = client.get("/analytics/search")
        assert r.status_code == 400
        assert "error" in r.json()

    def test_analytics_search_with_query(self, client):
        r = client.get("/analytics/search?q=test")
        assert r.status_code == 200
        data = r.json()
        assert "results" in data

    def test_analytics_timeline(self, client):
        r = client.get("/analytics/timeline")
        assert r.status_code == 200
        data = r.json()
        assert "timeline" in data


# --- Chatbot endpoint ---

class TestChatEndpoint:
    def test_chat_health(self, client):
        r = client.post("/chat", json={"message": "how's my system?"})
        assert r.status_code == 200
        data = r.json()
        assert data["intent"] == "health"
        assert "response" in data

    def test_chat_greeting(self, client):
        r = client.post("/chat", json={"message": "hello"})
        assert r.status_code == 200
        assert r.json()["intent"] == "general"

    def test_chat_disk(self, client):
        r = client.post("/chat", json={"message": "disk usage"})
        assert r.status_code == 200
        assert r.json()["intent"] == "disk"
        assert "data" in r.json()

    def test_chat_memory(self, client):
        r = client.post("/chat", json={"message": "how much ram"})
        assert r.status_code == 200
        assert r.json()["intent"] == "memory"

    def test_chat_cpu(self, client):
        r = client.post("/chat", json={"message": "cpu usage"})
        assert r.status_code == 200
        assert r.json()["intent"] == "cpu"

    def test_chat_empty_message(self, client):
        r = client.post("/chat", json={"message": ""})
        assert r.status_code == 200
        assert r.json()["intent"] == "empty"

    def test_chat_unsupported(self, client):
        r = client.post("/chat", json={"message": "battery level"})
        assert r.status_code == 200
        assert r.json()["intent"] == "unsupported"


# --- Platform endpoint ---

class TestPlatformEndpoint:
    def test_platform(self, client):
        r = client.get("/platform")
        assert r.status_code == 200
        data = r.json()
        assert "platform" in data


# --- Error handling ---

class TestErrorHandling:
    def test_404_returns_json(self, client):
        """Unknown routes should return structured JSON 404, not HTML."""
        r = client.get("/nonexistent/endpoint")
        assert r.status_code == 404
        data = r.json()
        assert "error" in data

    def test_task_not_found_returns_404(self, client):
        """Requesting a non-existent task should return 404."""
        r = client.get("/tasks/nonexistent-task-id")
        assert r.status_code == 404
        assert "error" in r.json()

    def test_context_missing_model_returns_400(self, client):
        """Context endpoint without model param should return 400."""
        r = client.get("/llm/context")
        assert r.status_code == 400
        data = r.json()
        assert "error" in data
        assert "model" in data["error"].lower()

    def test_search_missing_query_returns_400(self, client):
        """Analytics search without query should return 400."""
        r = client.get("/analytics/search")
        assert r.status_code == 400
        data = r.json()
        assert "error" in data

    def test_valid_endpoints_still_return_200(self, client):
        """Verify normal endpoints still work after error handling additions."""
        for path in ["/health", "/status", "/metrics", "/processes"]:
            r = client.get(path)
            assert r.status_code == 200, f"{path} returned {r.status_code}"
