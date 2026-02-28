"""Universal conversation health scoring -- single 0-100 number.

Combines up to seven signals into one intuitive score, adapting weights
based on which signals are available:

1. Context freshness (how full is the context window?)
2. Latency health (are responses getting slower?)
3. Cost efficiency (are you paying more for less output?)
4. Session fatigue (MCP session duration and tool call count)
5. Tool call burden (repeated tool patterns, frequency acceleration)
6. VRAM pressure (Ollama model memory allocation)
7. Inference throughput (local model tokens/second trend)

Higher score = healthier conversation.
"""

from __future__ import annotations

from bannin.log import logger


def calculate_health_score(
    context_percent: float,
    latency_ratio: float | None,
    cost_efficiency_trend: float | None,
    session_fatigue: dict | None = None,
    vram_pressure: float | None = None,
    inference_trend: float | None = None,
    model: str | None = None,
    weights: dict | None = None,
    thresholds: dict | None = None,
    client_label: str | None = None,
) -> dict:
    """Calculate a conversation health score from 0-100.

    Args:
        context_percent: How much of the context window is used (0-100).
        latency_ratio: Second-half avg latency / first-half avg latency.
                       1.0 = stable, 2.0 = doubled, None = not enough data.
        cost_efficiency_trend: Ratio of recent cost-per-output-token vs early.
                               1.0 = stable, 2.0 = paying double. None = not enough data.
        session_fatigue: Dict from MCPSessionTracker.get_session_health() with
                         session_fatigue (0-100) and tool_call_burden (0-100).
        vram_pressure: Ollama VRAM usage 0-100. None if no local LLM.
        inference_trend: Current tps / initial tps ratio. <1 = slowing.
                         None if no inference data.
        model: Model name for danger zone lookup.
        weights: Override scoring weights (from config).
        thresholds: Override rating thresholds (from config).

    Returns:
        Dict with health_score, rating, components, recommendation, danger_zone.
    """
    if thresholds is None:
        thresholds = _load_thresholds()

    # Determine which signals are available and their weights
    signal_weights = _resolve_weights(
        context_percent=context_percent,
        latency_ratio=latency_ratio,
        cost_efficiency_trend=cost_efficiency_trend,
        session_fatigue=session_fatigue,
        vram_pressure=vram_pressure,
        inference_trend=inference_trend,
        override=weights,
    )

    # --- Score each component ---
    components = {}

    # Context freshness
    danger_zone = _get_danger_zone(model)
    context_score = _score_context_freshness(context_percent, danger_zone)
    context_detail = _human_context_detail(context_score, context_percent)
    components["context_freshness"] = {
        "score": context_score,
        "weight": signal_weights.get("context_freshness", 0),
        "detail": context_detail,
    }

    # Latency health
    latency_score, latency_detail = _score_latency(latency_ratio)
    components["latency_health"] = {
        "score": latency_score,
        "weight": signal_weights.get("latency_health", 0),
        "detail": latency_detail,
    }

    # Cost efficiency
    cost_score, cost_detail = _score_cost_efficiency(cost_efficiency_trend)
    components["cost_efficiency"] = {
        "score": cost_score,
        "weight": signal_weights.get("cost_efficiency", 0),
        "detail": cost_detail,
    }

    # Session fatigue
    fatigue_val = 0.0
    if session_fatigue:
        fatigue_val = session_fatigue.get("session_fatigue", 0)
    fatigue_score = max(0, 100 - fatigue_val)
    fatigue_detail = _human_fatigue_detail(fatigue_score, session_fatigue)
    components["session_fatigue"] = {
        "score": fatigue_score,
        "weight": signal_weights.get("session_fatigue", 0),
        "detail": fatigue_detail,
    }

    # Chat degradation (replaces raw tool_call_burden)
    # Combines tool overhead + context growth rate into one user-facing signal
    burden_val = 0.0
    if session_fatigue:
        burden_val = session_fatigue.get("tool_call_burden", 0)
    burden_score = max(0, 100 - burden_val)
    degradation_detail = _human_degradation_detail(burden_score, context_percent, session_fatigue)
    components["chat_quality"] = {
        "score": burden_score,
        "weight": signal_weights.get("tool_call_burden", 0),
        "detail": degradation_detail,
    }

    # VRAM pressure (Ollama)
    vram_score = _score_vram_pressure(vram_pressure)
    components["vram_pressure"] = {
        "score": vram_score,
        "weight": signal_weights.get("vram_pressure", 0),
        "detail": f"VRAM at {vram_pressure:.0f}%" if vram_pressure is not None else "No VRAM data",
    }

    # Inference throughput (local LLM)
    inference_score, inference_detail = _score_inference_throughput(inference_trend)
    components["inference_throughput"] = {
        "score": inference_score,
        "weight": signal_weights.get("inference_throughput", 0),
        "detail": inference_detail,
    }

    # --- Weighted average ---
    health_score = 0.0
    for key, comp in components.items():
        w = comp["weight"]
        if w > 0:
            health_score += comp["score"] * w

    health_score = round(max(0, min(100, health_score)), 1)
    rating = _get_rating(health_score, thresholds)

    # Recommendation
    recommendation = _build_recommendation(health_score, components, session_fatigue, model, danger_zone, context_percent)

    # Determine source label
    source = _determine_source(session_fatigue, vram_pressure, inference_trend, cost_efficiency_trend, client_label)

    result = {
        "health_score": health_score,
        "rating": rating,
        "source": source,
        "components": {k: v for k, v in components.items() if v["weight"] > 0},
        "recommendation": recommendation,
    }

    if danger_zone is not None:
        result["danger_zone"] = {
            "model": model,
            "danger_zone_percent": danger_zone,
            "in_danger_zone": context_percent >= danger_zone,
        }

    return result


def _determine_source(
    session_fatigue: dict | None,
    vram_pressure: float | None,
    inference_trend: float | None,
    cost_efficiency_trend: float | None,
    client_label: str | None = None,
) -> str:
    """Determine a human-readable source label for the health score."""
    sources = []
    if session_fatigue is not None:
        # Use client_label from the pushed data or explicit parameter
        label = client_label or session_fatigue.get("client_label") or "Claude Code"
        sources.append(f"MCP Session ({label})")
    if vram_pressure is not None:
        sources.append("Ollama (Local LLM)")
    if cost_efficiency_trend is not None:
        sources.append("LLM API")
    if inference_trend is not None and "Ollama" not in " ".join(sources):
        sources.append("Local LLM")

    if not sources:
        return "No active LLM signals -- baseline score"

    return " + ".join(sources)


def _resolve_weights(
    context_percent: float,
    latency_ratio: float | None,
    cost_efficiency_trend: float | None,
    session_fatigue: dict | None,
    vram_pressure: float | None,
    inference_trend: float | None,
    override: dict | None = None,
) -> dict[str, float]:
    """Dynamically compute weights based on available signals.

    Unavailable signals get weight 0 and their weight redistributes
    proportionally to available signals.
    """
    if override:
        return override

    # Determine profile
    has_cost = cost_efficiency_trend is not None
    has_session = session_fatigue is not None
    has_vram = vram_pressure is not None
    has_inference = inference_trend is not None

    # Load profile from config
    profile = _load_weight_profile(has_cost, has_session, has_vram)

    # Build available signal set with desired weights
    available = {}
    for signal, weight in profile.items():
        if signal == "cost_efficiency" and not has_cost:
            continue
        if signal == "session_fatigue" and not has_session:
            continue
        if signal == "tool_call_burden" and not has_session:
            continue
        if signal == "vram_pressure" and not has_vram:
            continue
        if signal == "inference_throughput" and not has_inference:
            continue
        if signal == "latency_health" and latency_ratio is None:
            continue
        if weight > 0:
            available[signal] = weight

    # Always include context_freshness
    if "context_freshness" not in available:
        available["context_freshness"] = 0.45

    # Normalize to sum to 1.0
    total = sum(available.values())
    if total > 0:
        return {k: round(v / total, 3) for k, v in available.items()}
    return {"context_freshness": 1.0}


def _load_weight_profile(has_cost: bool, has_session: bool, has_vram: bool) -> dict[str, float]:
    """Load weight profile from config based on detected user type."""
    try:
        from bannin.config.loader import get_config
        cfg = get_config().get("intelligence", {}).get("conversation_health", {})
        profiles = cfg.get("weight_profiles", {})
    except Exception:
        logger.debug("Config unavailable for health weight profiles, using defaults")
        profiles = {}

    # Select profile based on signals
    if has_session:
        profile_name = "mcp"
    elif has_vram:
        profile_name = "local_llm"
    else:
        profile_name = "api"

    default_profiles = {
        "api": {
            "context_freshness": 0.45,
            "latency_health": 0.30,
            "cost_efficiency": 0.25,
            "session_fatigue": 0.0,
            "tool_call_burden": 0.0,
            "vram_pressure": 0.0,
            "inference_throughput": 0.0,
        },
        "mcp": {
            "context_freshness": 0.25,
            "latency_health": 0.15,
            "cost_efficiency": 0.0,
            "session_fatigue": 0.35,
            "tool_call_burden": 0.25,
            "vram_pressure": 0.0,
            "inference_throughput": 0.0,
        },
        "local_llm": {
            "context_freshness": 0.30,
            "latency_health": 0.30,
            "cost_efficiency": 0.0,
            "session_fatigue": 0.0,
            "tool_call_burden": 0.0,
            "vram_pressure": 0.25,
            "inference_throughput": 0.15,
        },
    }

    return profiles.get(profile_name, default_profiles.get(profile_name, default_profiles["api"]))


def _get_danger_zone(model: str | None) -> float | None:
    """Look up model-specific danger zone percentage from config."""
    if not model:
        return None
    try:
        from bannin.llm.pricing import lookup_model
        info = lookup_model(model)
        if info:
            dz = info.get("danger_zone_percent")
            if dz is not None:
                return float(dz)
    except Exception:
        logger.debug("Model lookup failed for danger zone: %s", model)
    # Default for unknown models
    try:
        from bannin.config.loader import get_config
        cfg = get_config().get("llm", {})
        return cfg.get("default_danger_zone_percent", 65)
    except Exception:
        logger.debug("Config unavailable for default danger zone, using 65%%")
        return 65


def _score_context_freshness(percent_used: float, danger_zone: float | None = None) -> float:
    """Score context freshness: 0-100. Less used = higher score.

    If a model-specific danger zone is set, scoring becomes more aggressive
    once context usage crosses that threshold.
    """
    if percent_used <= 0:
        return 100.0

    dz = danger_zone or 80  # Default fallback

    if percent_used <= dz * 0.6:
        return 100.0
    if percent_used <= dz:
        # Linear decay: 100 at 60% of dz -> 50 at dz
        return 100.0 - (percent_used - dz * 0.6) * (50.0 / (dz * 0.4))
    if percent_used <= 95:
        # In danger zone: rapid decay 50 -> 0
        span = 95 - dz
        if span > 0:
            return max(0.0, 50.0 - (percent_used - dz) * (50.0 / span))
        return 0.0
    return 0.0


def _score_latency(ratio: float | None) -> tuple[float, str]:
    """Score latency health: 0-100. Stable = high score."""
    if ratio is None:
        return 100.0, "Not enough data to assess latency"
    if ratio <= 1.0:
        return 100.0, "Latency stable or improving"
    if ratio <= 1.5:
        score = 100.0 - (ratio - 1.0) * (40.0 / 0.5)
        return round(score, 1), f"Latency slightly increased ({ratio:.1f}x)"
    if ratio <= 2.0:
        score = 60.0 - (ratio - 1.5) * (40.0 / 0.5)
        return round(score, 1), f"Latency degrading ({ratio:.1f}x slower)"
    if ratio <= 3.0:
        score = 20.0 - (ratio - 2.0) * (20.0 / 1.0)
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
    return round(max(0.0, 20.0 - (trend - 2.0) * 20.0), 1), f"Cost per response significantly increased ({trend:.1f}x)"


def _score_vram_pressure(vram_percent: float | None) -> float:
    """Score VRAM pressure: 0-100. Lower usage = higher score."""
    if vram_percent is None:
        return 100.0
    if vram_percent <= 50:
        return 100.0
    if vram_percent <= 75:
        return 100.0 - (vram_percent - 50) * (30.0 / 25.0)
    if vram_percent <= 90:
        return 70.0 - (vram_percent - 75) * (40.0 / 15.0)
    return max(0.0, 30.0 - (vram_percent - 90) * (30.0 / 10.0))


def _score_inference_throughput(trend: float | None) -> tuple[float, str]:
    """Score inference throughput: 0-100. Stable or improving = high score."""
    if trend is None:
        return 100.0, "No inference data"
    if trend >= 1.0:
        return 100.0, "Inference speed stable or improving"
    if trend >= 0.8:
        score = 100.0 - (1.0 - trend) * (40.0 / 0.2)
        return round(score, 1), f"Inference speed slightly decreased ({trend:.2f}x)"
    if trend >= 0.5:
        score = 60.0 - (0.8 - trend) * (40.0 / 0.3)
        return round(max(0, score), 1), f"Inference speed degrading ({trend:.2f}x)"
    return 0.0, f"Inference speed critically low ({trend:.2f}x of initial)"


def _load_thresholds() -> dict:
    try:
        from bannin.config.loader import get_config
        cfg = get_config().get("intelligence", {}).get("conversation_health", {})
        return cfg.get("thresholds", {"excellent": 90, "good": 70, "fair": 50, "poor": 30})
    except Exception:
        logger.debug("Config unavailable for health thresholds, using defaults")
        return {"excellent": 90, "good": 70, "fair": 50, "poor": 30}


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


def _build_recommendation(
    score: float,
    components: dict,
    session_fatigue: dict | None,
    model: str | None,
    danger_zone: float | None,
    context_percent: float,
) -> str | None:
    """Build the most relevant recommendation based on component scores."""
    if score >= 70:
        return None

    # Priority: most impactful component
    if score < 30:
        return "This conversation is losing quality. Summarize your progress and start a fresh session."

    if danger_zone and context_percent >= danger_zone:
        return "The AI is struggling to keep track of everything. A fresh conversation will give better results."

    if session_fatigue and session_fatigue.get("session_fatigue", 0) > 50:
        return "This session has been going a while. Consider summarizing key points and starting fresh."

    if score < 50:
        return "Quality is declining. A new conversation will give you better, more focused responses."

    return "Keep an eye on quality -- it may start declining as the conversation grows."


# --- Human-readable detail generators ---

def _human_context_detail(score: float, context_percent: float) -> str:
    """Plain-English explanation of context freshness."""
    if context_percent <= 0:
        return "No context data yet"
    if score >= 90:
        return "Conversation is fresh with plenty of room"
    if score >= 70:
        return "Good room remaining -- conversation quality is strong"
    if score >= 50:
        return "Past halfway -- still good, but plan for a new session soon"
    if score >= 30:
        return "Getting crowded -- responses may start losing earlier context"
    return "Nearly full -- start a new conversation for best quality"


def _human_fatigue_detail(score: float, session_fatigue: dict | None) -> str:
    """Plain-English explanation of session fatigue."""
    if session_fatigue is None:
        return "No session data"
    if score >= 90:
        return "Fresh session -- no signs of fatigue"
    if score >= 70:
        return "Session is healthy -- everything running smoothly"
    if score >= 50:
        return "Session has been running a while -- consider summarizing key points"
    if score >= 30:
        return "Extended session -- a fresh start would improve quality"
    return "Very long session -- summarize progress and start new for best results"


def _human_degradation_detail(
    burden_score: float,
    context_percent: float,
    session_fatigue: dict | None,
) -> str:
    """Plain-English explanation of chat quality / degradation."""
    # Combine tool burden + context pressure for overall degradation signal
    if burden_score >= 90 and context_percent < 50:
        return "No signs of quality loss -- conversation is clean"
    if burden_score >= 70:
        if context_percent < 60:
            return "Quality is holding steady"
        return "Quality is good, but context is filling up"
    if burden_score >= 50:
        return "Some quality pressure -- heavier tool use is filling context faster"
    if burden_score >= 30:
        return "Quality declining -- heavy activity is crowding the context window"
    return "Significant degradation -- too much context consumed, start fresh"
