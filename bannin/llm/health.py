"""Conversation health scoring — single 0-100 number.

Combines three signals into one intuitive score:
1. Context freshness (how full is the context window?)
2. Latency health (are responses getting slower?)
3. Cost efficiency (are you paying more for less output?)

Higher score = healthier conversation.
"""


def calculate_health_score(
    context_percent: float,
    latency_ratio: float | None,
    cost_efficiency_trend: float | None,
    weights: dict | None = None,
    thresholds: dict | None = None,
) -> dict:
    """Calculate a conversation health score from 0-100.

    Args:
        context_percent: How much of the context window is used (0-100)
        latency_ratio: Second-half avg latency / first-half avg latency.
                       1.0 = stable, 2.0 = doubled, None = not enough data
        cost_efficiency_trend: Ratio of recent cost-per-output-token vs early.
                               1.0 = stable, 2.0 = paying double. None = not enough data
        weights: Override scoring weights (from config)
        thresholds: Override rating thresholds (from config)

    Returns:
        Dict with health_score, rating, components, recommendation, etc.
    """
    if weights is None:
        weights = _load_weights()
    if thresholds is None:
        thresholds = _load_thresholds()

    # --- Component 1: Context freshness (higher = better) ---
    context_score = _score_context_freshness(context_percent)

    # --- Component 2: Latency health (higher = better) ---
    latency_score, latency_detail = _score_latency(latency_ratio)

    # --- Component 3: Cost efficiency (higher = better) ---
    cost_score, cost_detail = _score_cost_efficiency(cost_efficiency_trend)

    # --- Weighted average ---
    w_context = weights.get("context_freshness", 0.45)
    w_latency = weights.get("latency_health", 0.30)
    w_cost = weights.get("cost_efficiency", 0.25)

    health_score = round(
        context_score * w_context +
        latency_score * w_latency +
        cost_score * w_cost,
        1
    )

    # Clamp to 0-100
    health_score = max(0, min(100, health_score))

    # Rating label
    rating = _get_rating(health_score, thresholds)

    # Recommendation
    recommendation = None
    if health_score < 30:
        recommendation = "This conversation is severely degraded. Start a new chat immediately."
    elif health_score < 50:
        recommendation = "Consider starting a new conversation for better performance."

    return {
        "health_score": health_score,
        "rating": rating,
        "components": {
            "context_freshness": {
                "score": context_score,
                "weight": w_context,
                "detail": f"{context_percent}% of context window used",
            },
            "latency_health": {
                "score": latency_score,
                "weight": w_latency,
                "detail": latency_detail,
            },
            "cost_efficiency": {
                "score": cost_score,
                "weight": w_cost,
                "detail": cost_detail,
            },
        },
        "recommendation": recommendation,
    }


def _score_context_freshness(percent_used: float) -> float:
    """Score context freshness: 0-100. Less used = higher score."""
    if percent_used <= 0:
        return 100.0
    if percent_used <= 50:
        return 100.0
    if percent_used <= 75:
        # Linear decay: 100 at 50% → 60 at 75%
        return 100.0 - (percent_used - 50) * (40.0 / 25.0)
    if percent_used <= 90:
        # Linear decay: 60 at 75% → 20 at 90%
        return 60.0 - (percent_used - 75) * (40.0 / 15.0)
    # Linear decay: 20 at 90% → 0 at 100%
    return max(0.0, 20.0 - (percent_used - 90) * (20.0 / 10.0))


def _score_latency(ratio: float | None) -> tuple[float, str]:
    """Score latency health: 0-100. Stable = high score."""
    if ratio is None:
        return 100.0, "Not enough data to assess latency"
    if ratio <= 1.0:
        return 100.0, "Latency stable or improving"
    if ratio <= 1.5:
        score = 100.0 - (ratio - 1.0) * (40.0 / 0.5)  # 100 → 60
        return round(score, 1), f"Latency slightly increased ({ratio:.1f}x)"
    if ratio <= 2.0:
        score = 60.0 - (ratio - 1.5) * (40.0 / 0.5)  # 60 → 20
        return round(score, 1), f"Latency degrading ({ratio:.1f}x slower)"
    if ratio <= 3.0:
        score = 20.0 - (ratio - 2.0) * (20.0 / 1.0)  # 20 → 0
        return round(max(0, score), 1), f"Latency severely degraded ({ratio:.1f}x slower)"
    return 0.0, f"Latency extremely degraded ({ratio:.1f}x slower)"


def _score_cost_efficiency(trend: float | None) -> tuple[float, str]:
    """Score cost efficiency: 0-100. Stable cost = high score."""
    if trend is None:
        return 100.0, "Not enough data to assess cost efficiency"
    if trend <= 1.0:
        return 100.0, "Cost efficiency stable or improving"
    if trend <= 1.5:
        score = 100.0 - (trend - 1.0) * (40.0 / 0.5)
        return round(score, 1), f"Cost per response increasing slightly ({trend:.1f}x)"
    if trend <= 2.0:
        score = 60.0 - (trend - 1.5) * (40.0 / 0.5)
        return round(score, 1), f"Cost per response increasing ({trend:.1f}x more expensive)"
    return max(0.0, 20.0 - (trend - 2.0) * 20.0), f"Cost per response significantly increased ({trend:.1f}x)"


def _get_rating(score: float, thresholds: dict) -> str:
    if score >= thresholds.get("excellent", 90):
        return "excellent"
    if score >= thresholds.get("good", 70):
        return "good"
    if score >= thresholds.get("fair", 50):
        return "fair"
    if score >= thresholds.get("poor", 30):
        return "poor"
    return "critical"


def _load_weights() -> dict:
    try:
        from bannin.config.loader import get_config
        cfg = get_config().get("intelligence", {}).get("conversation_health", {})
        return cfg.get("weights", {"context_freshness": 0.45, "latency_health": 0.30, "cost_efficiency": 0.25})
    except Exception:
        return {"context_freshness": 0.45, "latency_health": 0.30, "cost_efficiency": 0.25}


def _load_thresholds() -> dict:
    try:
        from bannin.config.loader import get_config
        cfg = get_config().get("intelligence", {}).get("conversation_health", {})
        return cfg.get("thresholds", {"excellent": 90, "good": 70, "fair": 50, "poor": 30})
    except Exception:
        return {"excellent": 90, "good": 70, "fair": 50, "poor": 30}
