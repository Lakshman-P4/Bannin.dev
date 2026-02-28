"""Tests for OOM prediction engine.

Validates linear regression math, trend detection, severity classification,
time-to-full extrapolation, and edge cases (empty data, insufficient points,
stable/decreasing trends, GPU predictions).
"""

import time

import pytest

from bannin.intelligence.oom import OOMPredictor, _format_eta


# ---------------------------------------------------------------------------
# Linear regression (pure math -- no side effects)
# ---------------------------------------------------------------------------

class TestLinearRegression:
    """Tests for OOMPredictor._linear_regression static method."""

    def test_empty_input(self):
        slope, intercept, r2 = OOMPredictor._linear_regression([])
        assert slope == 0.0
        assert intercept == 0.0
        assert r2 == 0.0

    def test_single_point(self):
        slope, intercept, r2 = OOMPredictor._linear_regression([(0, 50)])
        assert slope == 0.0
        assert intercept == 0.0
        assert r2 == 0.0

    def test_perfect_positive_line(self):
        """y = 2x + 10 should give slope=2, intercept=10, R^2=1."""
        points = [(i, 2 * i + 10) for i in range(20)]
        slope, intercept, r2 = OOMPredictor._linear_regression(points)
        assert abs(slope - 2.0) < 1e-9
        assert abs(intercept - 10.0) < 1e-9
        assert abs(r2 - 1.0) < 1e-9

    def test_perfect_negative_line(self):
        """y = -0.5x + 80 should give slope=-0.5, R^2=1."""
        points = [(i, -0.5 * i + 80) for i in range(20)]
        slope, intercept, r2 = OOMPredictor._linear_regression(points)
        assert abs(slope - (-0.5)) < 1e-9
        assert abs(intercept - 80.0) < 1e-9
        assert abs(r2 - 1.0) < 1e-9

    def test_horizontal_line(self):
        """Constant y -> slope=0, R^2=0 (no variance)."""
        points = [(i, 42) for i in range(10)]
        slope, intercept, r2 = OOMPredictor._linear_regression(points)
        assert abs(slope) < 1e-9
        assert abs(intercept - 42.0) < 1e-9
        assert r2 == 0.0  # ss_tot == 0

    def test_same_x_values(self):
        """All x=0 -> denominator is 0, should return (0, mean_y, 0)."""
        points = [(0, 10), (0, 20), (0, 30)]
        slope, intercept, r2 = OOMPredictor._linear_regression(points)
        assert slope == 0.0
        assert abs(intercept - 20.0) < 1e-9  # mean of [10,20,30]
        assert r2 == 0.0

    def test_two_points(self):
        """Exactly two points -> perfect fit."""
        points = [(0, 10), (10, 20)]
        slope, intercept, r2 = OOMPredictor._linear_regression(points)
        assert abs(slope - 1.0) < 1e-9
        assert abs(intercept - 10.0) < 1e-9
        assert abs(r2 - 1.0) < 1e-9

    def test_noisy_data_r_squared(self):
        """Noisy data should have 0 < R^2 < 1."""
        # y = x with noise
        import random
        random.seed(42)
        points = [(i, i + random.gauss(0, 5)) for i in range(50)]
        slope, intercept, r2 = OOMPredictor._linear_regression(points)
        assert slope > 0.5  # should still detect upward trend
        assert 0.0 <= r2 <= 1.0

    def test_r_squared_clamped(self):
        """R^2 should never exceed [0, 1]."""
        # Very noisy data that might produce negative R^2 before clamping
        points = [(0, 100), (1, 0), (2, 100), (3, 0), (4, 100)]
        slope, intercept, r2 = OOMPredictor._linear_regression(points)
        assert 0.0 <= r2 <= 1.0


# ---------------------------------------------------------------------------
# _predict_from_series (trend detection + severity)
# ---------------------------------------------------------------------------

class TestPredictFromSeries:
    """Tests for the core prediction logic."""

    def _make_predictor(self, min_points=12, confidence_threshold=70):
        p = OOMPredictor.__new__(OOMPredictor)
        p._min_points = min_points
        p._confidence_threshold = confidence_threshold
        return p

    def test_increasing_trend(self):
        """Linearly increasing memory -> 'increasing' trend."""
        p = self._make_predictor()
        # 0.1% per second growth, starting at 60%
        points = [(i * 2, 60 + i * 0.2) for i in range(30)]
        result = p._predict_from_series(points, current=66.0)
        assert result["trend"] == "increasing"
        assert result["growth_rate_per_min"] > 0
        assert result["minutes_until_full"] is not None
        assert result["minutes_until_full"] > 0

    def test_decreasing_trend(self):
        """Linearly decreasing memory -> 'decreasing' trend, no time-to-full."""
        p = self._make_predictor()
        points = [(i * 2, 80 - i * 0.2) for i in range(30)]
        result = p._predict_from_series(points, current=74.0)
        assert result["trend"] == "decreasing"
        assert result["growth_rate_per_min"] < 0
        assert result["minutes_until_full"] is None
        assert result["severity"] == "ok"

    def test_stable_trend(self):
        """Flat memory -> 'stable' trend."""
        p = self._make_predictor()
        points = [(i * 2, 50.0) for i in range(30)]
        result = p._predict_from_series(points, current=50.0)
        assert result["trend"] == "stable"
        assert result["minutes_until_full"] is None
        assert result["severity"] == "ok"

    def test_severity_critical(self):
        """Fast growth near full -> critical severity."""
        p = self._make_predictor(confidence_threshold=0)  # skip confidence gate
        # 1% per second starting at 95%
        points = [(i, 90 + i * 1.0) for i in range(15)]
        result = p._predict_from_series(points, current=95.0)
        assert result["trend"] == "increasing"
        assert result["severity"] == "critical"
        assert result["minutes_until_full"] <= 5

    def test_severity_warning(self):
        """Moderate growth -> warning severity."""
        p = self._make_predictor(confidence_threshold=0)
        # Growth that reaches 100% in ~10 minutes
        # 0.05%/sec = 3%/min, at 70% -> 30%/3 = 10min
        points = [(i * 2, 70 + i * 0.1) for i in range(30)]
        result = p._predict_from_series(points, current=73.0)
        assert result["trend"] == "increasing"
        if result["minutes_until_full"] <= 15:
            assert result["severity"] == "warning"

    def test_severity_info(self):
        """Slow growth far from full -> info severity."""
        p = self._make_predictor(confidence_threshold=0)
        # 0.05%/sec = 3%/min, at 30% -> 70%/3 = ~23min -> info (>15min)
        points = [(i * 2, 30 + i * 0.1) for i in range(30)]
        result = p._predict_from_series(points, current=33.0)
        assert result["trend"] == "increasing"
        assert result["severity"] == "info"

    def test_low_confidence_overrides_severity(self):
        """When confidence < threshold, severity should be 'low_confidence'."""
        p = self._make_predictor(confidence_threshold=99)  # very high bar
        # Very few noisy points -> low R^2
        points = [(0, 50), (10, 51), (20, 49), (30, 52), (40, 48),
                  (50, 53), (60, 47), (70, 54), (80, 46), (90, 55),
                  (100, 44), (110, 56)]
        result = p._predict_from_series(points, current=56.0)
        if result["trend"] == "increasing":
            assert result["severity"] == "low_confidence"

    def test_minutes_until_full_positive(self):
        """Time-to-full should always be positive when trend is increasing."""
        p = self._make_predictor(confidence_threshold=0)
        points = [(i, 50 + i * 0.5) for i in range(20)]
        result = p._predict_from_series(points, current=60.0)
        if result["trend"] == "increasing":
            assert result["minutes_until_full"] > 0


# ---------------------------------------------------------------------------
# _predict_ram (full path through MetricHistory)
# ---------------------------------------------------------------------------

class TestPredictRam:
    def _make_predictor(self, min_points=12):
        p = OOMPredictor.__new__(OOMPredictor)
        p._min_points = min_points
        p._confidence_threshold = 70
        return p

    def test_empty_readings(self):
        p = self._make_predictor()
        result = p._predict_ram([])
        assert result["trend"] == "no_data"
        assert result["current_percent"] is None

    def test_insufficient_readings(self):
        p = self._make_predictor(min_points=12)
        now = time.time()
        readings = [{"epoch": now + i, "ram_percent": 50.0} for i in range(5)]
        result = p._predict_ram(readings)
        assert result["trend"] == "insufficient_data"
        assert result["data_points"] == 5
        assert result["current_percent"] == 50.0

    def test_sufficient_stable_readings(self):
        p = self._make_predictor(min_points=5)
        now = time.time()
        readings = [{"epoch": now + i * 2, "ram_percent": 45.0} for i in range(20)]
        result = p._predict_ram(readings)
        assert result["trend"] == "stable"
        assert result["current_percent"] == 45.0


# ---------------------------------------------------------------------------
# _predict_gpu
# ---------------------------------------------------------------------------

class TestPredictGpu:
    def _make_predictor(self, min_points=5):
        p = OOMPredictor.__new__(OOMPredictor)
        p._min_points = min_points
        p._confidence_threshold = 70
        return p

    def test_no_gpu_data(self):
        p = self._make_predictor()
        result = p._predict_gpu([])
        assert result == []

    def test_no_gpu_key(self):
        p = self._make_predictor()
        readings = [{"epoch": time.time(), "ram_percent": 50}]
        result = p._predict_gpu(readings)
        assert result == []

    def test_single_gpu_insufficient(self):
        p = self._make_predictor(min_points=10)
        now = time.time()
        readings = [
            {"epoch": now + i, "ram_percent": 50, "gpu": [{"memory_percent": 40, "name": "RTX 4090"}]}
            for i in range(3)
        ]
        result = p._predict_gpu(readings)
        assert len(result) == 1
        assert result[0]["trend"] == "insufficient_data"
        assert result[0]["name"] == "RTX 4090"

    def test_single_gpu_stable(self):
        p = self._make_predictor(min_points=5)
        now = time.time()
        readings = [
            {"epoch": now + i * 2, "ram_percent": 50, "gpu": [{"memory_percent": 60.0, "name": "RTX 4090"}]}
            for i in range(20)
        ]
        result = p._predict_gpu(readings)
        assert len(result) == 1
        assert result[0]["trend"] == "stable"
        assert result[0]["index"] == 0

    def test_multi_gpu(self):
        p = self._make_predictor(min_points=5)
        now = time.time()
        readings = [
            {
                "epoch": now + i * 2,
                "ram_percent": 50,
                "gpu": [
                    {"memory_percent": 50.0, "name": "GPU 0"},
                    {"memory_percent": 60.0, "name": "GPU 1"},
                ],
            }
            for i in range(10)
        ]
        result = p._predict_gpu(readings)
        assert len(result) == 2
        assert result[0]["name"] == "GPU 0"
        assert result[1]["name"] == "GPU 1"


# ---------------------------------------------------------------------------
# _format_eta helper
# ---------------------------------------------------------------------------

class TestFormatEta:
    def test_zero_seconds(self):
        assert _format_eta(0) == "now"

    def test_negative_seconds(self):
        assert _format_eta(-10) == "now"

    def test_minutes_only(self):
        assert _format_eta(300) == "~5m from now"

    def test_hours_and_minutes(self):
        assert _format_eta(3900) == "~1h 5m from now"

    def test_exact_hour(self):
        assert _format_eta(3600) == "~1h 0m from now"
