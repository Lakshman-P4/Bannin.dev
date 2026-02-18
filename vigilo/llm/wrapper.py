"""Client wrappers that intercept LLM API calls for tracking.

Usage:
    import vigilo
    from openai import OpenAI

    client = vigilo.wrap(OpenAI())
    response = client.chat.completions.create(model="gpt-4o", messages=[...])
    # ^ Vigilo automatically tracks tokens, cost, and latency
"""

import time

from vigilo.llm.tracker import LLMTracker, track

_WRAPPED_MARKER = "_vigilo_wrapped"


def wrap(client):
    """Wrap an LLM client for automatic token/cost tracking.

    Supports:
        - openai.OpenAI() and openai.AzureOpenAI()
        - anthropic.Anthropic()
        - google.generativeai.GenerativeModel()

    The client is returned as-is (same object) with tracking added.
    All existing functionality is preserved — only the API call methods
    are wrapped to capture usage data after each call.
    """
    if getattr(client, _WRAPPED_MARKER, False):
        return client  # Already wrapped, don't double-wrap

    client_module = type(client).__module__ or ""
    client_class = type(client).__name__

    if "openai" in client_module:
        _wrap_openai(client)
    elif "anthropic" in client_module:
        _wrap_anthropic(client)
    elif "google" in client_module and "generative" in client_module:
        _wrap_google(client)
    elif client_class in ("OpenAI", "AzureOpenAI", "AsyncOpenAI"):
        _wrap_openai(client)
    elif client_class in ("Anthropic", "AsyncAnthropic"):
        _wrap_anthropic(client)
    elif client_class == "GenerativeModel":
        _wrap_google(client)
    else:
        raise TypeError(
            f"vigilo.wrap() does not recognize client type '{client_class}' "
            f"(module: {client_module}). "
            f"Supported: OpenAI, AzureOpenAI, Anthropic, GenerativeModel."
        )

    setattr(client, _WRAPPED_MARKER, True)
    return client


# ---------------------------------------------------------------------------
# OpenAI wrapper
# ---------------------------------------------------------------------------

def _wrap_openai(client):
    """Wrap OpenAI client's chat.completions.create method."""
    tracker = LLMTracker.get()

    # Detect provider from base URL (for OpenAI-compatible providers)
    provider = "openai"
    base_url = getattr(client, "base_url", None)
    if base_url:
        url_str = str(base_url).lower()
        if "azure" in url_str or type(client).__name__ == "AzureOpenAI":
            provider = "azure_openai"
        elif "x.ai" in url_str:
            provider = "xai"
        elif "together" in url_str:
            provider = "together"
        elif "fireworks" in url_str:
            provider = "fireworks"
        elif "groq" in url_str:
            provider = "groq"
        elif "localhost" in url_str or "127.0.0.1" in url_str:
            provider = "local"

    try:
        original_create = client.chat.completions.create
    except AttributeError:
        return  # Client doesn't have the expected structure

    def wrapped_create(*args, **kwargs):
        start = time.time()
        response = original_create(*args, **kwargs)
        latency = time.time() - start

        # Extract usage from response
        try:
            _record_openai_usage(tracker, response, kwargs.get("model", "unknown"), latency, provider)
        except Exception:
            pass  # Never break the user's code

        return response

    client.chat.completions.create = wrapped_create


def _record_openai_usage(tracker, response, model, latency, provider):
    """Extract token usage from an OpenAI response and record it."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    # Cached tokens (if available)
    cached_tokens = 0
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    if prompt_details:
        cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0

    # Use model from response if available (more accurate than kwargs)
    actual_model = getattr(response, "model", model)

    scope = track.current_scope()

    tracker.record(
        provider=provider,
        model=actual_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_seconds=latency,
        cached_tokens=cached_tokens,
        conversation_id=scope,
    )


# ---------------------------------------------------------------------------
# Anthropic wrapper
# ---------------------------------------------------------------------------

def _wrap_anthropic(client):
    """Wrap Anthropic client's messages.create method."""
    tracker = LLMTracker.get()

    try:
        original_create = client.messages.create
    except AttributeError:
        return

    def wrapped_create(*args, **kwargs):
        start = time.time()
        response = original_create(*args, **kwargs)
        latency = time.time() - start

        try:
            _record_anthropic_usage(tracker, response, kwargs.get("model", "unknown"), latency)
        except Exception:
            pass

        return response

    client.messages.create = wrapped_create


def _record_anthropic_usage(tracker, response, model, latency):
    """Extract token usage from an Anthropic response and record it."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return

    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cached_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0

    actual_model = getattr(response, "model", model)
    scope = track.current_scope()

    tracker.record(
        provider="anthropic",
        model=actual_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_seconds=latency,
        cached_tokens=cached_tokens,
        conversation_id=scope,
    )


# ---------------------------------------------------------------------------
# Google Generative AI wrapper
# ---------------------------------------------------------------------------

def _wrap_google(model):
    """Wrap Google GenerativeModel's generate_content method."""
    tracker = LLMTracker.get()

    try:
        original_generate = model.generate_content
    except AttributeError:
        return

    # Get model name from the GenerativeModel object
    model_name = getattr(model, "model_name", None) or getattr(model, "_model_name", "unknown")
    # Strip "models/" prefix if present
    if isinstance(model_name, str) and model_name.startswith("models/"):
        model_name = model_name[7:]

    def wrapped_generate(*args, **kwargs):
        start = time.time()
        response = original_generate(*args, **kwargs)
        latency = time.time() - start

        try:
            _record_google_usage(tracker, response, model_name, latency)
        except Exception:
            pass

        return response

    model.generate_content = wrapped_generate


def _record_google_usage(tracker, response, model_name, latency):
    """Extract token usage from a Google Gemini response and record it."""
    # usage_metadata can be on the response directly or accessed via attribute
    metadata = getattr(response, "usage_metadata", None)
    if metadata is None:
        return

    input_tokens = getattr(metadata, "prompt_token_count", 0) or 0
    output_tokens = getattr(metadata, "candidates_token_count", 0) or 0
    cached_tokens = getattr(metadata, "cached_content_token_count", 0) or 0

    scope = track.current_scope()

    tracker.record(
        provider="google",
        model=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_seconds=latency,
        cached_tokens=cached_tokens,
        conversation_id=scope,
    )
