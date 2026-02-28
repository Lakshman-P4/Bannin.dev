"""Shared fixtures for Bannin test suite."""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# All singleton classes that have a .reset() classmethod.
# Auto-reset between test modules prevents leaked state across tests.
# ---------------------------------------------------------------------------

_SINGLETON_CLASSES = [
    "bannin.analytics.store.AnalyticsStore",
    "bannin.analytics.pipeline.EventPipeline",
    "bannin.intelligence.alerts.ThresholdEngine",
    "bannin.intelligence.history.MetricHistory",
    "bannin.intelligence.progress.ProgressTracker",
    "bannin.llm.tracker.LLMTracker",
    "bannin.llm.ollama.OllamaMonitor",
    "bannin.llm.connections.LLMConnectionScanner",
    "bannin.llm.claude_session.ClaudeSessionReader",
    "bannin.mcp.session.MCPSessionTracker",
    "bannin.intelligence.training.TrainingDetector",
]


def _reset_all_singletons():
    """Reset every singleton that has been imported."""
    import importlib
    for path in _SINGLETON_CLASSES:
        module_path, class_name = path.rsplit(".", 1)
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name, None)
            if cls is not None and hasattr(cls, "reset"):
                cls.reset()
        except (ImportError, AttributeError):
            pass


@pytest.fixture(autouse=True, scope="module")
def _reset_singletons_between_modules():
    """Auto-reset all singletons at the start of every test module."""
    _reset_all_singletons()
    yield
    _reset_all_singletons()


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient backed by the Bannin app."""
    from bannin.api import app
    return TestClient(app)
