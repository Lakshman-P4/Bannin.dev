"""Client wrappers that intercept LLM API calls for tracking.

Usage:
    import bannin
    from openai import OpenAI

    client = bannin.wrap(OpenAI())
    response = client.chat.completions.create(model="gpt-4o", messages=[...])
    # ^ Bannin automatically tracks tokens, cost, and latency

Streaming is also supported:
    response = client.chat.completions.create(model="gpt-4o", messages=[...], stream=True)
    for chunk in response:
        print(chunk.choices[0].delta.content, end="")
    # ^ Bannin captures usage from the final streaming chunk automatically
"""

from __future__ import annotations

import threading
import time

from typing import Any, Iterator

from bannin.log import logger
from bannin.llm.tracker import LLMTracker, track

_WRAPPED_MARKER = "_bannin_wrapped"
_wrap_lock = threading.Lock()


def wrap(client: object) -> object:
    """Wrap an LLM client for automatic token/cost tracking.

    Supports:
        - openai.OpenAI() and openai.AzureOpenAI()
        - anthropic.Anthropic()
        - google.generativeai.GenerativeModel()

    The client is returned as-is (same object) with tracking added.
    All existing functionality is preserved — only the API call methods
    are wrapped to capture usage data after each call.

    Both streaming and non-streaming calls are tracked.
    """
    # Atomic check+set prevents double-wrapping from concurrent threads
    with _wrap_lock:
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
                f"bannin.wrap(): unrecognized client type '{client_class}' "
                f"(module: {client_module}). "
                f"Supported: OpenAI, AzureOpenAI, Anthropic, GenerativeModel."
            )

        setattr(client, _WRAPPED_MARKER, True)
    return client


# ---------------------------------------------------------------------------
# OpenAI wrapper
# ---------------------------------------------------------------------------

def _wrap_openai(client: object) -> None:
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

    def wrapped_create(*args: object, **kwargs: object) -> object:
        is_streaming = kwargs.get("stream", False)

        if is_streaming:
            # Copy kwargs to avoid mutating the caller's dict
            kwargs = dict(kwargs)
            if "stream_options" not in kwargs:
                kwargs["stream_options"] = {"include_usage": True}
            elif isinstance(kwargs["stream_options"], dict):
                kwargs["stream_options"] = dict(kwargs["stream_options"])
                kwargs["stream_options"].setdefault("include_usage", True)

            start = time.time()
            stream = original_create(*args, **kwargs)
            scope = track.current_scope()
            model = kwargs.get("model", "unknown")
            return _OpenAIStreamProxy(stream, tracker, model, provider, start, scope)
        else:
            start = time.time()
            response = original_create(*args, **kwargs)
            latency = time.time() - start

            try:
                _record_openai_usage(tracker, response, kwargs.get("model", "unknown"), latency, provider)
            except Exception:
                logger.debug("Failed to record OpenAI usage")

            return response

    try:
        client.chat.completions.create = wrapped_create
    except (AttributeError, TypeError):
        logger.debug("Cannot wrap OpenAI client -- read-only attribute")
        return


class _OpenAIStreamProxy:
    """Transparent proxy that yields OpenAI stream chunks and captures usage from the final chunk."""

    def __init__(self, stream: object, tracker: LLMTracker, model: str, provider: str, start_time: float, scope: str | None) -> None:
        self._stream = stream
        self._tracker = tracker
        self._model = model
        self._provider = provider
        self._start_time = start_time
        self._scope = scope
        self._recorded = False

    def __iter__(self) -> Iterator:
        for chunk in self._stream:
            # The final chunk has empty choices and contains usage data
            usage = getattr(chunk, "usage", None)
            if usage is not None and not getattr(chunk, "choices", None):
                try:
                    latency = time.time() - self._start_time
                    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                    output_tokens = getattr(usage, "completion_tokens", 0) or 0
                    cached_tokens = 0
                    prompt_details = getattr(usage, "prompt_tokens_details", None)
                    if prompt_details:
                        cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0
                    actual_model = getattr(chunk, "model", self._model)

                    self._tracker.record(
                        provider=self._provider,
                        model=actual_model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_seconds=latency,
                        cached_tokens=cached_tokens,
                        conversation_id=self._scope,
                    )
                    self._recorded = True
                except Exception:
                    logger.debug("Failed to record OpenAI streaming usage")
            yield chunk

    def __enter__(self) -> _OpenAIStreamProxy:
        if hasattr(self._stream, "__enter__"):
            self._stream.__enter__()
        return self

    def __exit__(self, *args: object) -> bool:
        if not self._recorded:
            logger.debug("OpenAI stream exited before usage chunk received; partial data lost")
        if hasattr(self._stream, "__exit__"):
            return self._stream.__exit__(*args)
        return False

    def close(self) -> None:
        if not self._recorded:
            logger.debug("OpenAI stream closed before usage chunk received; partial data lost")
        if hasattr(self._stream, "close"):
            self._stream.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _record_openai_usage(tracker: LLMTracker, response: object, model: str, latency: float, provider: str) -> None:
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

def _wrap_anthropic(client: object) -> None:
    """Wrap Anthropic client's messages.create method."""
    tracker = LLMTracker.get()

    try:
        original_create = client.messages.create
    except AttributeError:
        return

    def wrapped_create(*args: object, **kwargs: object) -> object:
        is_streaming = kwargs.get("stream", False)

        if is_streaming:
            start = time.time()
            stream = original_create(*args, **kwargs)
            scope = track.current_scope()
            model = kwargs.get("model", "unknown")
            return _AnthropicStreamProxy(stream, tracker, model, start, scope)
        else:
            start = time.time()
            response = original_create(*args, **kwargs)
            latency = time.time() - start

            try:
                _record_anthropic_usage(tracker, response, kwargs.get("model", "unknown"), latency)
            except Exception:
                logger.debug("Failed to record Anthropic usage")

            return response

    try:
        client.messages.create = wrapped_create
    except (AttributeError, TypeError):
        logger.debug("Cannot wrap Anthropic client -- read-only attribute")
        return


class _AnthropicStreamProxy:
    """Transparent proxy that yields Anthropic stream events and captures usage."""

    def __init__(self, stream: object, tracker: LLMTracker, model: str, start_time: float, scope: str | None) -> None:
        self._stream = stream
        self._tracker = tracker
        self._model = model
        self._start_time = start_time
        self._scope = scope
        self._input_tokens = 0
        self._output_tokens = 0
        self._cached_tokens = 0
        self._actual_model = model
        self._recorded = False

    def __iter__(self) -> Iterator:
        for event in self._stream:
            event_type = getattr(event, "type", "")

            if event_type == "message_start":
                msg = getattr(event, "message", None)
                if msg:
                    usage = getattr(msg, "usage", None)
                    if usage:
                        self._input_tokens = getattr(usage, "input_tokens", 0) or 0
                    self._actual_model = getattr(msg, "model", self._model)

            elif event_type == "message_delta":
                usage = getattr(event, "usage", None)
                if usage:
                    self._output_tokens = getattr(usage, "output_tokens", 0) or 0
                    self._cached_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0

            elif event_type == "message_stop":
                self._record_usage()

            yield event

    def _record_usage(self) -> None:
        """Record accumulated usage data. Safe to call multiple times."""
        if self._recorded:
            return
        try:
            latency = time.time() - self._start_time
            self._tracker.record(
                provider="anthropic",
                model=self._actual_model,
                input_tokens=self._input_tokens,
                output_tokens=self._output_tokens,
                latency_seconds=latency,
                cached_tokens=self._cached_tokens,
                conversation_id=self._scope,
            )
            self._recorded = True
        except Exception:
            logger.debug("Failed to record Anthropic streaming usage")

    def __enter__(self) -> _AnthropicStreamProxy:
        if hasattr(self._stream, "__enter__"):
            self._stream.__enter__()
        return self

    def __exit__(self, *args: object) -> bool:
        # Record partial data if stream exited before message_stop
        self._record_usage()
        if hasattr(self._stream, "__exit__"):
            return self._stream.__exit__(*args)
        return False

    def close(self) -> None:
        # Record partial data if stream was closed before message_stop
        self._record_usage()
        if hasattr(self._stream, "close"):
            self._stream.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _record_anthropic_usage(tracker: LLMTracker, response: object, model: str, latency: float) -> None:
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

def _wrap_google(model: object) -> None:
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

    def wrapped_generate(*args: object, **kwargs: object) -> object:
        is_streaming = kwargs.get("stream", False)

        if is_streaming:
            start = time.time()
            stream = original_generate(*args, **kwargs)
            scope = track.current_scope()
            return _GoogleStreamProxy(stream, tracker, model_name, start, scope)
        else:
            start = time.time()
            response = original_generate(*args, **kwargs)
            latency = time.time() - start

            try:
                _record_google_usage(tracker, response, model_name, latency)
            except Exception:
                logger.debug("Failed to record Google usage")

            return response

    try:
        model.generate_content = wrapped_generate
    except (AttributeError, TypeError):
        logger.debug("Cannot wrap Google GenerativeModel -- read-only attribute")
        return


class _GoogleStreamProxy:
    """Transparent proxy that yields Google Gemini stream chunks and captures usage from the last chunk."""

    def __init__(self, stream: object, tracker: LLMTracker, model_name: str, start_time: float, scope: str | None) -> None:
        self._stream = stream
        self._tracker = tracker
        self._model_name = model_name
        self._start_time = start_time
        self._scope = scope
        self._last_chunk = None
        self._recorded = False

    def __iter__(self) -> Iterator:
        for chunk in self._stream:
            self._last_chunk = chunk
            yield chunk

        # Stream finished — extract usage from the last chunk
        self._record_usage()

    def _record_usage(self) -> None:
        """Record usage from the last chunk. Safe to call multiple times."""
        if self._recorded or self._last_chunk is None:
            return
        try:
            latency = time.time() - self._start_time
            metadata = getattr(self._last_chunk, "usage_metadata", None)
            if metadata:
                input_tokens = getattr(metadata, "prompt_token_count", 0) or 0
                output_tokens = getattr(metadata, "candidates_token_count", 0) or 0
                cached_tokens = getattr(metadata, "cached_content_token_count", 0) or 0

                self._tracker.record(
                    provider="google",
                    model=self._model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_seconds=latency,
                    cached_tokens=cached_tokens,
                    conversation_id=self._scope,
                )
            self._recorded = True
        except Exception:
            logger.debug("Failed to record Google streaming usage")

    def __enter__(self) -> _GoogleStreamProxy:
        if hasattr(self._stream, "__enter__"):
            self._stream.__enter__()
        return self

    def __exit__(self, *args: object) -> bool:
        # Record partial data if stream exited before full iteration
        self._record_usage()
        if hasattr(self._stream, "__exit__"):
            return self._stream.__exit__(*args)
        return False

    def close(self) -> None:
        # Record partial data if stream was closed before full iteration
        self._record_usage()
        if hasattr(self._stream, "close"):
            self._stream.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


def _record_google_usage(tracker: LLMTracker, response: object, model_name: str, latency: float) -> None:
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
