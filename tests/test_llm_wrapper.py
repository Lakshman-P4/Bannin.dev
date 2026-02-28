"""Tests for LLM client wrappers.

Validates client type detection, double-wrap prevention, token extraction
from mock responses, streaming proxy behavior, and provider detection
from base URLs.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from bannin.llm.wrapper import wrap, _WRAPPED_MARKER


# ---------------------------------------------------------------------------
# Helpers: mock client classes that mimic real SDK structure
# ---------------------------------------------------------------------------

def _make_openai_client(module="openai.resources", class_name="OpenAI", base_url=None):
    """Create a mock OpenAI-like client."""
    client = MagicMock()
    type(client).__module__ = module
    type(client).__name__ = class_name
    if base_url:
        client.base_url = base_url
    else:
        client.base_url = "https://api.openai.com/v1"
    # Ensure _bannin_wrapped is not set
    delattr(client, _WRAPPED_MARKER) if hasattr(client, _WRAPPED_MARKER) else None
    client.configure_mock(**{_WRAPPED_MARKER: False})
    # Properly set up the spec check
    type(client)._bannin_wrapped = False
    return client


def _make_anthropic_client(module="anthropic._client", class_name="Anthropic"):
    client = MagicMock()
    type(client).__module__ = module
    type(client).__name__ = class_name
    type(client)._bannin_wrapped = False
    return client


def _make_google_client(module="google.generativeai.generative_models", class_name="GenerativeModel"):
    client = MagicMock()
    type(client).__module__ = module
    type(client).__name__ = class_name
    type(client)._bannin_wrapped = False
    client.model_name = "models/gemini-1.5-pro"
    return client


def _make_unknown_client(module="some.random.module", class_name="RandomClient"):
    client = MagicMock()
    type(client).__module__ = module
    type(client).__name__ = class_name
    type(client)._bannin_wrapped = False
    return client


# ---------------------------------------------------------------------------
# Client type detection
# ---------------------------------------------------------------------------

class TestClientTypeDetection:
    def test_openai_by_module(self):
        client = _make_openai_client(module="openai.resources")
        result = wrap(client)
        assert result is client
        assert getattr(client, _WRAPPED_MARKER) is True

    def test_anthropic_by_module(self):
        client = _make_anthropic_client()
        result = wrap(client)
        assert result is client
        assert getattr(client, _WRAPPED_MARKER) is True

    def test_google_by_module(self):
        client = _make_google_client()
        result = wrap(client)
        assert result is client
        assert getattr(client, _WRAPPED_MARKER) is True

    def test_openai_by_class_name(self):
        """When module doesn't match, fall back to class name."""
        client = _make_openai_client(module="custom_module", class_name="OpenAI")
        result = wrap(client)
        assert result is client
        assert getattr(client, _WRAPPED_MARKER) is True

    def test_azure_by_class_name(self):
        client = _make_openai_client(module="custom_module", class_name="AzureOpenAI")
        result = wrap(client)
        assert getattr(client, _WRAPPED_MARKER) is True

    def test_async_openai_by_class_name(self):
        client = _make_openai_client(module="custom_module", class_name="AsyncOpenAI")
        result = wrap(client)
        assert getattr(client, _WRAPPED_MARKER) is True

    def test_anthropic_by_class_name(self):
        client = _make_anthropic_client(module="custom", class_name="Anthropic")
        result = wrap(client)
        assert getattr(client, _WRAPPED_MARKER) is True

    def test_async_anthropic_by_class_name(self):
        client = _make_anthropic_client(module="custom", class_name="AsyncAnthropic")
        result = wrap(client)
        assert getattr(client, _WRAPPED_MARKER) is True

    def test_generative_model_by_class_name(self):
        client = _make_google_client(module="custom", class_name="GenerativeModel")
        result = wrap(client)
        assert getattr(client, _WRAPPED_MARKER) is True

    def test_unknown_client_raises(self):
        client = _make_unknown_client()
        with pytest.raises(TypeError, match="unrecognized client type"):
            wrap(client)


# ---------------------------------------------------------------------------
# Double-wrap prevention
# ---------------------------------------------------------------------------

class TestDoubleWrapPrevention:
    def test_no_double_wrap(self):
        client = _make_openai_client()
        wrap(client)
        original_create = client.chat.completions.create

        # Wrapping again should be a no-op
        wrap(client)
        assert client.chat.completions.create is original_create

    def test_marker_set_after_wrap(self):
        client = _make_openai_client()
        assert getattr(client, _WRAPPED_MARKER, False) is False
        wrap(client)
        assert getattr(client, _WRAPPED_MARKER) is True


# ---------------------------------------------------------------------------
# OpenAI non-streaming token extraction
# ---------------------------------------------------------------------------

class TestOpenAITokenExtraction:
    def test_records_usage_from_response(self):
        client = _make_openai_client()
        original_fn = MagicMock()

        # Mock response with usage data
        response = MagicMock()
        response.usage.prompt_tokens = 100
        response.usage.completion_tokens = 50
        response.usage.prompt_tokens_details = None
        response.model = "gpt-4o"
        original_fn.return_value = response

        client.chat.completions.create = original_fn

        with patch("bannin.llm.wrapper.LLMTracker") as MockTracker:
            tracker_instance = MockTracker.get.return_value
            wrap(client)
            # Call the wrapped function
            result = client.chat.completions.create(model="gpt-4o", messages=[])

        assert result is response
        tracker_instance.record.assert_called_once()
        call_kwargs = tracker_instance.record.call_args
        assert call_kwargs[1]["input_tokens"] == 100
        assert call_kwargs[1]["output_tokens"] == 50
        assert call_kwargs[1]["model"] == "gpt-4o"

    def test_no_usage_on_response(self):
        """If response has no usage attr, should not crash."""
        client = _make_openai_client()
        response = MagicMock(spec=[])  # no attributes
        response.usage = None
        client.chat.completions.create = MagicMock(return_value=response)

        with patch("bannin.llm.wrapper.LLMTracker"):
            wrap(client)
            result = client.chat.completions.create(model="gpt-4o", messages=[])
        assert result is response


# ---------------------------------------------------------------------------
# Provider detection from base URL
# ---------------------------------------------------------------------------

class TestProviderDetection:
    def test_azure_base_url(self):
        client = _make_openai_client(base_url="https://my-resource.openai.azure.com/v1")
        with patch("bannin.llm.wrapper.LLMTracker") as MockTracker:
            tracker_instance = MockTracker.get.return_value
            response = MagicMock()
            response.usage.prompt_tokens = 10
            response.usage.completion_tokens = 5
            response.usage.prompt_tokens_details = None
            response.model = "gpt-4"
            client.chat.completions.create = MagicMock(return_value=response)
            wrap(client)
            client.chat.completions.create(model="gpt-4", messages=[])

        call_kwargs = tracker_instance.record.call_args[1]
        assert call_kwargs["provider"] == "azure_openai"

    def test_groq_base_url(self):
        client = _make_openai_client(base_url="https://api.groq.com/openai/v1")
        with patch("bannin.llm.wrapper.LLMTracker") as MockTracker:
            tracker_instance = MockTracker.get.return_value
            response = MagicMock()
            response.usage.prompt_tokens = 10
            response.usage.completion_tokens = 5
            response.usage.prompt_tokens_details = None
            response.model = "llama3-70b"
            client.chat.completions.create = MagicMock(return_value=response)
            wrap(client)
            client.chat.completions.create(model="llama3-70b", messages=[])

        call_kwargs = tracker_instance.record.call_args[1]
        assert call_kwargs["provider"] == "groq"

    def test_localhost_base_url(self):
        client = _make_openai_client(base_url="http://localhost:11434/v1")
        with patch("bannin.llm.wrapper.LLMTracker") as MockTracker:
            tracker_instance = MockTracker.get.return_value
            response = MagicMock()
            response.usage.prompt_tokens = 10
            response.usage.completion_tokens = 5
            response.usage.prompt_tokens_details = None
            response.model = "llama3"
            client.chat.completions.create = MagicMock(return_value=response)
            wrap(client)
            client.chat.completions.create(model="llama3", messages=[])

        call_kwargs = tracker_instance.record.call_args[1]
        assert call_kwargs["provider"] == "local"


# ---------------------------------------------------------------------------
# Anthropic non-streaming token extraction
# ---------------------------------------------------------------------------

class TestAnthropicTokenExtraction:
    def test_records_usage(self):
        client = _make_anthropic_client()
        response = MagicMock()
        response.usage.input_tokens = 200
        response.usage.output_tokens = 80
        response.usage.cache_read_input_tokens = 50
        response.model = "claude-sonnet-4-20250514"
        client.messages.create = MagicMock(return_value=response)

        with patch("bannin.llm.wrapper.LLMTracker") as MockTracker:
            tracker_instance = MockTracker.get.return_value
            wrap(client)
            client.messages.create(model="claude-sonnet-4-20250514", messages=[])

        call_kwargs = tracker_instance.record.call_args[1]
        assert call_kwargs["input_tokens"] == 200
        assert call_kwargs["output_tokens"] == 80
        assert call_kwargs["cached_tokens"] == 50
        assert call_kwargs["provider"] == "anthropic"


# ---------------------------------------------------------------------------
# Google non-streaming token extraction
# ---------------------------------------------------------------------------

class TestGoogleTokenExtraction:
    def test_records_usage(self):
        client = _make_google_client()
        response = MagicMock()
        response.usage_metadata.prompt_token_count = 150
        response.usage_metadata.candidates_token_count = 60
        response.usage_metadata.cached_content_token_count = 0
        client.generate_content = MagicMock(return_value=response)

        with patch("bannin.llm.wrapper.LLMTracker") as MockTracker:
            tracker_instance = MockTracker.get.return_value
            wrap(client)
            client.generate_content(contents="Hello")

        call_kwargs = tracker_instance.record.call_args[1]
        assert call_kwargs["input_tokens"] == 150
        assert call_kwargs["output_tokens"] == 60
        assert call_kwargs["provider"] == "google"
        assert call_kwargs["model"] == "gemini-1.5-pro"  # stripped "models/" prefix

    def test_model_name_prefix_stripped(self):
        client = _make_google_client()
        client.model_name = "models/gemini-2.0-flash"
        response = MagicMock()
        response.usage_metadata.prompt_token_count = 10
        response.usage_metadata.candidates_token_count = 5
        response.usage_metadata.cached_content_token_count = 0
        client.generate_content = MagicMock(return_value=response)

        with patch("bannin.llm.wrapper.LLMTracker") as MockTracker:
            tracker_instance = MockTracker.get.return_value
            wrap(client)
            client.generate_content(contents="Hi")

        call_kwargs = tracker_instance.record.call_args[1]
        assert call_kwargs["model"] == "gemini-2.0-flash"


# ---------------------------------------------------------------------------
# OpenAI streaming proxy
# ---------------------------------------------------------------------------

class TestOpenAIStreamProxy:
    def test_stream_yields_all_chunks(self):
        from bannin.llm.wrapper import _OpenAIStreamProxy

        chunks = [MagicMock(choices=["c"], usage=None) for _ in range(3)]
        # Final chunk with usage
        final = MagicMock()
        final.choices = []
        final.usage = MagicMock()
        final.usage.prompt_tokens = 100
        final.usage.completion_tokens = 50
        final.usage.prompt_tokens_details = None
        final.model = "gpt-4o"
        chunks.append(final)

        tracker = MagicMock()
        proxy = _OpenAIStreamProxy(
            stream=iter(chunks),
            tracker=tracker,
            model="gpt-4o",
            provider="openai",
            start_time=time.time() - 1,
            scope=None,
        )

        collected = list(proxy)
        assert len(collected) == 4
        tracker.record.assert_called_once()

    def test_stream_context_manager(self):
        from bannin.llm.wrapper import _OpenAIStreamProxy

        mock_stream = MagicMock()
        mock_stream.__iter__ = MagicMock(return_value=iter([]))
        proxy = _OpenAIStreamProxy(mock_stream, MagicMock(), "m", "p", time.time(), None)
        with proxy as p:
            assert p is proxy
