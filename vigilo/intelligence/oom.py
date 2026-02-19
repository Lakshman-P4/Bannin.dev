"""OOM (Out-Of-Memory) prediction engine.

Uses the metric history ring buffer to detect memory growth trends and
predict when RAM or GPU VRAM will be exhausted.  All math is pure Python
(no numpy) so the package stays lightweight.
"""

import time

from vigilo.intelligence.history import MetricHistory


class OOMPredictor:
    """Predicts out-of-memory events from memory usage trends."""

    def __init__(self):
        try:
            from vigilo.config.loader import get_config
            cfg = get_config().get("intelligence", {}).get("oom", {})
            self._min_points = cfg.get("min_data_points", 12)
            self._confidence_threshold = cfg.get("confidence_threshold", 70)
        except Exception:
            self._min_points = 12
            self._confidence_threshold = 70

    def predict(self) -> dict:
        """Generate OOM predictions for RAM and each GPU.

        Returns a dict with 'ram' and 'gpu' predictions.
        """
        history = MetricHistory.get()
        readings = history.get_full_history(last_n_minutes=30)

        return {
            "ram": self._predict_ram(readings),
            "gpu": self._predict_gpu(readings),
            "data_points": len(readings),
            "min_data_points_required": self._min_points,
        }

    def _predict_ram(self, readings: list[dict]) -> dict:
        """Predict RAM exhaustion."""
        if not readings:
            return self._insufficient_data(label="ram")

        current = readings[-1]["ram_percent"]

        # Need enough data points for meaningful prediction
        if len(readings) < self._min_points:
            return {
                "current_percent": current,
                "trend": "insufficient_data",
                "data_points": len(readings),
                "note": f"Need at least {self._min_points} readings for prediction (have {len(readings)})",
            }

        # Extract time series: (elapsed_seconds, percent)
        t0 = readings[0]["epoch"]
        points = [(r["epoch"] - t0, r["ram_percent"]) for r in readings]

        return self._predict_from_series(points, current, label="ram")

    def _predict_gpu(self, readings: list[dict]) -> list[dict]:
        """Predict GPU VRAM exhaustion for each GPU."""
        # Find readings that have GPU data
        gpu_readings = [r for r in readings if "gpu" in r and r["gpu"]]
        if not gpu_readings:
            return []

        # Determine how many GPUs we have from the latest reading
        num_gpus = len(gpu_readings[-1]["gpu"])
        results = []

        for gpu_idx in range(num_gpus):
            # Filter readings that have this GPU index
            valid = [r for r in gpu_readings if gpu_idx < len(r["gpu"])]
            if not valid:
                continue

            current = valid[-1]["gpu"][gpu_idx]["memory_percent"]
            gpu_name = valid[-1]["gpu"][gpu_idx].get("name", f"GPU {gpu_idx}")

            if len(valid) < self._min_points:
                results.append({
                    "index": gpu_idx,
                    "name": gpu_name,
                    "current_percent": current,
                    "trend": "insufficient_data",
                    "data_points": len(valid),
                    "note": f"Need at least {self._min_points} readings",
                })
                continue

            t0 = valid[0]["epoch"]
            points = [(r["epoch"] - t0, r["gpu"][gpu_idx]["memory_percent"]) for r in valid]
            prediction = self._predict_from_series(points, current, label=gpu_name)
            prediction["index"] = gpu_idx
            prediction["name"] = gpu_name
            results.append(prediction)

        return results

    def _predict_from_series(self, points: list[tuple], current: float, label: str = "") -> dict:
        """Core prediction: linear regression on (time, percent) data.

        Returns prediction dict with trend, growth rate, time to full, confidence.
        """
        slope, intercept, r_squared = self._linear_regression(points)

        # Determine trend from slope
        if slope > 0.01:  # Growing more than 0.01% per second (~0.6%/min)
            trend = "increasing"
        elif slope < -0.01:
            trend = "decreasing"
        else:
            trend = "stable"

        # Growth rate in percent per minute
        growth_rate_per_min = round(slope * 60, 3)

        # Confidence: based on R-squared and number of points
        # R-squared tells us how well a straight line fits the data
        # More points = more reliable
        point_factor = min(1.0, len(points) / 60)  # Scales up to 60 points
        confidence = round(r_squared * 100 * point_factor, 1)

        result = {
            "current_percent": current,
            "trend": trend,
            "growth_rate_per_min": growth_rate_per_min,
            "confidence": confidence,
            "data_points": len(points),
        }

        # Predict time to 100% (only if memory is growing)
        if trend == "increasing" and slope > 0:
            remaining_percent = 100.0 - current
            seconds_to_full = remaining_percent / slope
            minutes_to_full = round(seconds_to_full / 60, 1)

            result["minutes_until_full"] = minutes_to_full
            result["estimated_full_at"] = _format_eta(seconds_to_full)

            # Severity based on time remaining and confidence
            if confidence >= self._confidence_threshold:
                if minutes_to_full <= 5:
                    result["severity"] = "critical"
                elif minutes_to_full <= 15:
                    result["severity"] = "warning"
                else:
                    result["severity"] = "info"
            else:
                result["severity"] = "low_confidence"
        else:
            result["minutes_until_full"] = None
            result["severity"] = "ok"

        return result

    def _insufficient_data(self, label: str = "") -> dict:
        return {
            "current_percent": None,
            "trend": "no_data",
            "note": "No metric history available. Wait for readings to accumulate.",
        }

    @staticmethod
    def _linear_regression(points: list[tuple]) -> tuple[float, float, float]:
        """Pure-Python least-squares linear regression.

        Args:
            points: list of (x, y) tuples

        Returns:
            (slope, intercept, r_squared)
        """
        n = len(points)
        if n < 2:
            return 0.0, 0.0, 0.0

        sum_x = sum(p[0] for p in points)
        sum_y = sum(p[1] for p in points)
        sum_xy = sum(p[0] * p[1] for p in points)
        sum_x2 = sum(p[0] ** 2 for p in points)
        sum_y2 = sum(p[1] ** 2 for p in points)

        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 0.0, sum_y / n, 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n

        # R-squared (coefficient of determination)
        mean_y = sum_y / n
        ss_tot = sum((p[1] - mean_y) ** 2 for p in points)
        ss_res = sum((p[1] - (slope * p[0] + intercept)) ** 2 for p in points)

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        # Clamp to [0, 1] — negative R² means the fit is worse than the mean
        r_squared = max(0.0, min(1.0, r_squared))

        return slope, intercept, r_squared


def _format_eta(seconds_from_now: float) -> str:
    """Format seconds-from-now as a human-readable ETA string."""
    if seconds_from_now <= 0:
        return "now"
    minutes = int(seconds_from_now // 60)
    if minutes < 60:
        return f"~{minutes}m from now"
    hours = minutes // 60
    remaining_min = minutes % 60
    return f"~{hours}h {remaining_min}m from now"
