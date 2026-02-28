"""LLM model pricing and context window data.

Prices are loaded from remote config (defaults.json → cache → GitHub)
so they stay current without a package release.
"""

from __future__ import annotations

from bannin.log import logger
from bannin.config.loader import get_config

# Hardcoded fallback — used only if config loading completely fails
_FALLBACK_MODELS = {
    # OpenAI
    "gpt-4o": {"provider": "openai", "input_per_m": 2.50, "output_per_m": 10.00, "cached_input_per_m": 1.25, "context_window": 128000},
    "gpt-4o-mini": {"provider": "openai", "input_per_m": 0.15, "output_per_m": 0.60, "cached_input_per_m": 0.075, "context_window": 128000},
    # Anthropic
    "claude-sonnet-4-20250514": {"provider": "anthropic", "input_per_m": 3.00, "output_per_m": 15.00, "cached_input_per_m": 0.30, "context_window": 200000},
    "claude-haiku-3-5-20241022": {"provider": "anthropic", "input_per_m": 0.80, "output_per_m": 4.00, "cached_input_per_m": 0.08, "context_window": 200000},
    # Google
    "gemini-2.0-flash": {"provider": "google", "input_per_m": 0.10, "output_per_m": 0.40, "cached_input_per_m": 0.025, "context_window": 1048576},
}


def _get_model_db() -> dict[str, dict]:
    """Load model database from config, falling back to hardcoded values."""
    try:
        cfg = get_config()
        models = cfg.get("llm", {}).get("models", {})
        if models:
            return models
    except Exception:
        logger.debug("Config unavailable for model database, using fallback")
    # Return a shallow copy so callers cannot corrupt the global fallback
    return dict(_FALLBACK_MODELS)


def lookup_model(model_name: str) -> dict | None:
    """Look up model info by name. Tries exact match, then prefix match.

    Returns dict with keys: provider, input_per_m, output_per_m, context_window, etc.
    Returns None if model is unknown.
    """
    db = _get_model_db()

    # Exact match — return a copy to prevent caller mutation of the db
    if model_name in db:
        return dict(db[model_name])

    # Prefix match -- strip date suffixes (e.g., "gpt-4o-2024-08-06" matches "gpt-4o")
    # Also handles "claude-sonnet-4-6" matching "claude-sonnet-4-20250514"
    # Use longest match to avoid "gpt-4o-mini" matching "gpt-4o" pricing.
    best_match: dict | None = None
    best_len = 0
    for known_name, info in db.items():
        if model_name.startswith(known_name) and len(known_name) > best_len:
            best_match = info
            best_len = len(known_name)
        elif known_name.startswith(model_name) and len(model_name) > best_len:
            best_match = info
            best_len = len(model_name)

    return dict(best_match) if best_match is not None else None


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Calculate cost in USD for a single API call.

    Returns 0.0 if the model is unknown (we still track tokens, just can't price them).
    """
    # Clamp to non-negative to guard against garbage values
    input_tokens = max(0, input_tokens)
    output_tokens = max(0, output_tokens)
    cached_tokens = max(0, cached_tokens)

    info = lookup_model(model)
    if info is None:
        return 0.0

    input_price = info.get("input_per_m", 0)
    output_price = info.get("output_per_m", 0)
    cached_price = info.get("cached_input_per_m", input_price)

    # Cached tokens are part of input_tokens but billed at a lower rate
    regular_input = max(0, input_tokens - cached_tokens)

    cost = (
        (regular_input / 1_000_000) * input_price
        + (cached_tokens / 1_000_000) * cached_price
        + (output_tokens / 1_000_000) * output_price
    )
    return round(cost, 6)


def get_context_window(model: str) -> int | None:
    """Get the context window size (in tokens) for a model. Returns None if unknown."""
    info = lookup_model(model)
    if info is None:
        return None
    return info.get("context_window")


def get_provider(model: str) -> str | None:
    """Get the provider name for a model. Returns None if unknown."""
    info = lookup_model(model)
    if info is None:
        return None
    return info.get("provider")
