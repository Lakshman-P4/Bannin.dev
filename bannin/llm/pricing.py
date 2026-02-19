"""LLM model pricing and context window data.

Prices are loaded from remote config (defaults.json → cache → GitHub)
so they stay current without a package release.
"""

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


def _get_model_db() -> dict:
    """Load model database from config, falling back to hardcoded values."""
    try:
        cfg = get_config()
        models = cfg.get("llm", {}).get("models", {})
        if models:
            return models
    except Exception:
        pass
    return _FALLBACK_MODELS


def lookup_model(model_name: str) -> dict | None:
    """Look up model info by name. Tries exact match, then prefix match.

    Returns dict with keys: provider, input_per_m, output_per_m, context_window, etc.
    Returns None if model is unknown.
    """
    db = _get_model_db()

    # Exact match
    if model_name in db:
        return db[model_name]

    # Prefix match — strip date suffixes (e.g., "gpt-4o-2024-08-06" → "gpt-4o")
    # Also handles "claude-sonnet-4-6" matching "claude-sonnet-4-20250514"
    for known_name, info in db.items():
        if model_name.startswith(known_name) or known_name.startswith(model_name):
            return info

    # Partial match — check if any known name is a substring
    model_lower = model_name.lower()
    for known_name, info in db.items():
        if known_name.lower() in model_lower or model_lower in known_name.lower():
            return info

    return None


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Calculate cost in USD for a single API call.

    Returns 0.0 if the model is unknown (we still track tokens, just can't price them).
    """
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
