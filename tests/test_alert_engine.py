"""Tests for the threshold alert engine.

Validates rule evaluation, cooldown enforcement, metric path resolution,
condition parsing, platform filtering, message formatting, and alert
history management.
"""

import time

import pytest

from bannin.intelligence.alerts import ThresholdEngine, _format_seconds, _OPERATORS


# ---------------------------------------------------------------------------
# Metric path resolution
# ---------------------------------------------------------------------------

class TestResolveMetric:
    """Tests for ThresholdEngine._resolve_metric."""

    def _engine(self):
        e = ThresholdEngine.__new__(ThresholdEngine)
        e._rules = []
        e._alert_history = []
        e._last_fired = {}
        e._data_lock = __import__("threading").RLock()
        e._current_platform = "local"
        return e

    def test_simple_path(self):
        e = self._engine()
        snapshot = {"memory": {"percent": 75.2}}
        assert e._resolve_metric("memory.percent", snapshot) == 75.2

    def test_nested_path(self):
        e = self._engine()
        snapshot = {"predictions": {"oom": {"ram": {"confidence": 85}}}}
        assert e._resolve_metric("predictions.oom.ram.confidence", snapshot) == 85

    def test_missing_key(self):
        e = self._engine()
        snapshot = {"memory": {"percent": 75}}
        assert e._resolve_metric("memory.missing", snapshot) is None

    def test_missing_intermediate(self):
        e = self._engine()
        snapshot = {"memory": {"percent": 75}}
        assert e._resolve_metric("cpu.percent", snapshot) is None

    def test_top_level_key(self):
        e = self._engine()
        snapshot = {"value": 42}
        assert e._resolve_metric("value", snapshot) == 42

    def test_empty_path(self):
        e = self._engine()
        assert e._resolve_metric("", {"": 5}) == 5

    def test_non_dict_intermediate(self):
        e = self._engine()
        snapshot = {"memory": 42}
        assert e._resolve_metric("memory.percent", snapshot) is None


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------

class TestEvaluateCondition:
    def _engine(self):
        e = ThresholdEngine.__new__(ThresholdEngine)
        e._rules = []
        e._alert_history = []
        e._last_fired = {}
        e._data_lock = __import__("threading").RLock()
        e._current_platform = "local"
        return e

    def test_simple_ge(self):
        e = self._engine()
        snapshot = {"predictions": {"oom": {"ram": {"confidence": 85}}}}
        assert e._evaluate_condition("predictions.oom.ram.confidence >= 70", snapshot) is True

    def test_simple_lt(self):
        e = self._engine()
        snapshot = {"predictions": {"oom": {"ram": {"confidence": 50}}}}
        assert e._evaluate_condition("predictions.oom.ram.confidence >= 70", snapshot) is False

    def test_missing_metric_returns_false(self):
        e = self._engine()
        assert e._evaluate_condition("missing.path >= 50", {}) is False

    def test_bad_format_returns_false(self):
        """Unparseable condition returns False (fail safe, don't fire on bad config)."""
        e = self._engine()
        assert e._evaluate_condition("invalid-condition", {}) is False

    def test_invalid_threshold_returns_false(self):
        e = self._engine()
        assert e._evaluate_condition("memory.percent >= notanumber", {"memory": {"percent": 80}}) is False

    def test_unknown_operator_returns_false(self):
        e = self._engine()
        assert e._evaluate_condition("memory.percent ~= 50", {"memory": {"percent": 80}}) is False


# ---------------------------------------------------------------------------
# Rule evaluation (evaluate method)
# ---------------------------------------------------------------------------

class TestEvaluate:
    def _engine_with_rules(self, rules):
        import collections
        e = ThresholdEngine.__new__(ThresholdEngine)
        e._rules = rules
        e._alert_history = collections.deque(maxlen=2000)
        e._last_fired = {}
        e._data_lock = __import__("threading").RLock()
        e._current_platform = "local"
        return e

    def test_fires_on_threshold_exceeded(self):
        rules = [{
            "id": "test_high_mem",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 80,
            "severity": "warning",
            "message": "Memory at {value}%",
            "cooldown_seconds": 60,
        }]
        e = self._engine_with_rules(rules)
        snapshot = {"memory": {"percent": 90.5}}
        alerts = e.evaluate(snapshot)
        assert len(alerts) == 1
        assert alerts[0]["id"] == "test_high_mem"
        assert alerts[0]["severity"] == "warning"
        assert "90.5" in alerts[0]["message"]

    def test_no_fire_below_threshold(self):
        rules = [{
            "id": "test_high_mem",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 80,
            "severity": "warning",
            "message": "Memory at {value}%",
            "cooldown_seconds": 60,
        }]
        e = self._engine_with_rules(rules)
        snapshot = {"memory": {"percent": 50.0}}
        alerts = e.evaluate(snapshot)
        assert len(alerts) == 0

    def test_cooldown_prevents_refire(self):
        rules = [{
            "id": "test_cd",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 80,
            "severity": "info",
            "message": "High memory",
            "cooldown_seconds": 300,
        }]
        e = self._engine_with_rules(rules)
        snapshot = {"memory": {"percent": 95}}

        # First evaluation fires
        alerts1 = e.evaluate(snapshot)
        assert len(alerts1) == 1

        # Second evaluation within cooldown does not fire
        alerts2 = e.evaluate(snapshot)
        assert len(alerts2) == 0

    def test_fires_after_cooldown_expires(self):
        rules = [{
            "id": "test_cd2",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 80,
            "severity": "info",
            "message": "High memory",
            "cooldown_seconds": 0,  # no cooldown
        }]
        e = self._engine_with_rules(rules)
        snapshot = {"memory": {"percent": 95}}

        alerts1 = e.evaluate(snapshot)
        assert len(alerts1) == 1
        alerts2 = e.evaluate(snapshot)
        assert len(alerts2) == 1  # fires again (0s cooldown)

    def test_platform_filter_blocks(self):
        rules = [{
            "id": "colab_only",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 50,
            "severity": "info",
            "message": "High memory on Colab",
            "cooldown_seconds": 60,
            "platforms": ["colab"],
        }]
        e = self._engine_with_rules(rules)
        e._current_platform = "local"
        alerts = e.evaluate({"memory": {"percent": 90}})
        assert len(alerts) == 0

    def test_platform_filter_allows(self):
        rules = [{
            "id": "colab_only",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 50,
            "severity": "info",
            "message": "High memory on Colab",
            "cooldown_seconds": 60,
            "platforms": ["colab"],
        }]
        e = self._engine_with_rules(rules)
        e._current_platform = "colab"
        alerts = e.evaluate({"memory": {"percent": 90}})
        assert len(alerts) == 1

    def test_platform_all_matches_everything(self):
        rules = [{
            "id": "all_plat",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 50,
            "severity": "info",
            "message": "msg",
            "cooldown_seconds": 60,
            "platforms": ["all"],
        }]
        e = self._engine_with_rules(rules)
        e._current_platform = "kaggle"
        alerts = e.evaluate({"memory": {"percent": 90}})
        assert len(alerts) == 1

    def test_additional_condition_blocks(self):
        rules = [{
            "id": "cond_test",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 80,
            "severity": "info",
            "message": "msg",
            "cooldown_seconds": 60,
            "condition": "predictions.oom.ram.confidence >= 70",
        }]
        e = self._engine_with_rules(rules)
        snapshot = {
            "memory": {"percent": 90},
            "predictions": {"oom": {"ram": {"confidence": 50}}},
        }
        alerts = e.evaluate(snapshot)
        assert len(alerts) == 0  # condition not met

    def test_additional_condition_allows(self):
        rules = [{
            "id": "cond_test2",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 80,
            "severity": "info",
            "message": "msg",
            "cooldown_seconds": 60,
            "condition": "predictions.oom.ram.confidence >= 70",
        }]
        e = self._engine_with_rules(rules)
        snapshot = {
            "memory": {"percent": 90},
            "predictions": {"oom": {"ram": {"confidence": 85}}},
        }
        alerts = e.evaluate(snapshot)
        assert len(alerts) == 1

    def test_missing_metric_skips_rule(self):
        rules = [{
            "id": "missing",
            "metric": "gpu.temperature",
            "operator": ">=",
            "threshold": 80,
            "severity": "info",
            "message": "Hot GPU",
            "cooldown_seconds": 60,
        }]
        e = self._engine_with_rules(rules)
        alerts = e.evaluate({"memory": {"percent": 50}})
        assert len(alerts) == 0

    def test_compare_to_another_metric(self):
        rules = [{
            "id": "compare_test",
            "metric": "memory.percent",
            "operator": ">",
            "compare_to": "disk.percent",
            "severity": "info",
            "message": "Memory exceeds disk usage: {value}%",
            "cooldown_seconds": 60,
        }]
        e = self._engine_with_rules(rules)
        snapshot = {"memory": {"percent": 80}, "disk": {"percent": 50}}
        alerts = e.evaluate(snapshot)
        assert len(alerts) == 1

    def test_compare_to_not_triggered(self):
        rules = [{
            "id": "compare_test2",
            "metric": "memory.percent",
            "operator": ">",
            "compare_to": "disk.percent",
            "severity": "info",
            "message": "msg",
            "cooldown_seconds": 60,
        }]
        e = self._engine_with_rules(rules)
        snapshot = {"memory": {"percent": 30}, "disk": {"percent": 50}}
        alerts = e.evaluate(snapshot)
        assert len(alerts) == 0

    def test_value_human_formatting(self):
        rules = [{
            "id": "eta_test",
            "metric": "tasks.longest_eta_seconds",
            "operator": ">=",
            "threshold": 60,
            "severity": "info",
            "message": "ETA: {value_human}",
            "cooldown_seconds": 60,
        }]
        e = self._engine_with_rules(rules)
        snapshot = {"tasks": {"longest_eta_seconds": 3700}}
        alerts = e.evaluate(snapshot)
        assert len(alerts) == 1
        assert "1h" in alerts[0]["message"]

    def test_multiple_rules_fire_independently(self):
        rules = [
            {
                "id": "rule_a",
                "metric": "memory.percent",
                "operator": ">=",
                "threshold": 80,
                "severity": "warning",
                "message": "Memory high",
                "cooldown_seconds": 60,
            },
            {
                "id": "rule_b",
                "metric": "cpu.percent",
                "operator": ">=",
                "threshold": 90,
                "severity": "warning",
                "message": "CPU high",
                "cooldown_seconds": 60,
            },
        ]
        e = self._engine_with_rules(rules)
        snapshot = {"memory": {"percent": 95}, "cpu": {"percent": 95}}
        alerts = e.evaluate(snapshot)
        assert len(alerts) == 2
        ids = {a["id"] for a in alerts}
        assert ids == {"rule_a", "rule_b"}


# ---------------------------------------------------------------------------
# Alert history
# ---------------------------------------------------------------------------

class TestAlertHistory:
    def _engine_with_fired_alerts(self, count):
        import collections
        e = ThresholdEngine.__new__(ThresholdEngine)
        e._rules = [{
            "id": "test",
            "metric": "memory.percent",
            "operator": ">=",
            "threshold": 50,
            "severity": "info",
            "message": "msg",
            "cooldown_seconds": 0,
        }]
        e._alert_history = collections.deque(maxlen=2000)
        e._last_fired = {}
        e._data_lock = __import__("threading").RLock()
        e._current_platform = "local"

        for i in range(count):
            e.evaluate({"memory": {"percent": 90}})
        return e

    def test_get_alerts_returns_newest_first(self):
        e = self._engine_with_fired_alerts(5)
        result = e.get_alerts()
        assert result["total_fired"] == 5
        alerts = result["alerts"]
        assert len(alerts) == 5
        # Newest should be first (reversed order)
        epochs = [a["fired_epoch"] for a in alerts]
        assert epochs == sorted(epochs, reverse=True)

    def test_get_alerts_with_limit(self):
        e = self._engine_with_fired_alerts(10)
        result = e.get_alerts(limit=3)
        assert len(result["alerts"]) == 3
        assert result["total_fired"] == 10


# ---------------------------------------------------------------------------
# Operator map
# ---------------------------------------------------------------------------

class TestOperators:
    def test_ge(self):
        assert _OPERATORS[">="](80, 70) is True
        assert _OPERATORS[">="](70, 70) is True
        assert _OPERATORS[">="](60, 70) is False

    def test_le(self):
        assert _OPERATORS["<="](60, 70) is True
        assert _OPERATORS["<="](70, 70) is True
        assert _OPERATORS["<="](80, 70) is False

    def test_gt(self):
        assert _OPERATORS[">"](80, 70) is True
        assert _OPERATORS[">"](70, 70) is False

    def test_lt(self):
        assert _OPERATORS["<"](60, 70) is True
        assert _OPERATORS["<"](70, 70) is False

    def test_eq(self):
        assert _OPERATORS["=="](70, 70) is True
        assert _OPERATORS["=="](71, 70) is False

    def test_ne(self):
        assert _OPERATORS["!="](71, 70) is True
        assert _OPERATORS["!="](70, 70) is False


# ---------------------------------------------------------------------------
# _format_seconds helper
# ---------------------------------------------------------------------------

class TestFormatSeconds:
    def test_seconds_only(self):
        assert _format_seconds(45) == "45s"

    def test_minutes_and_seconds(self):
        assert _format_seconds(125) == "2m 5s"

    def test_hours_and_minutes(self):
        assert _format_seconds(3700) == "1h 1m"

    def test_zero(self):
        assert _format_seconds(0) == "0s"

    def test_float_input(self):
        assert _format_seconds(90.5) == "1m 30s"

    def test_invalid_input(self):
        assert _format_seconds("abc") == "abc"
