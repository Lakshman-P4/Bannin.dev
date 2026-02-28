"""Tests for chatbot intent detection.

Validates that _detect_intent correctly classifies user messages into
the expected intent categories. Social/greeting messages now route to
the 'general' fallback since the chatbot is data-driven only.
"""

import pytest
from bannin.intelligence.chat import _detect_intent


# --- Unsupported ---

@pytest.mark.parametrize("msg", [
    "check my battery",
    "how's my wifi",
    "bluetooth status",
    "what's the weather",
    "set a timer",
    "play music",
    "launch chrome",
    "take a screenshot",
    "what's my password",
])
def test_unsupported(msg):
    assert _detect_intent(msg) == "unsupported"


# --- History ---

@pytest.mark.parametrize("msg", [
    "what happened while I was away",
    "what did i miss",
    "any alerts",
    "recent events",
    "event log",
    "history",
    "alerts",
    "past alerts",
    "anything happen while I was gone",
])
def test_history(msg):
    assert _detect_intent(msg) == "history"


# --- Ollama ---

@pytest.mark.parametrize("msg", [
    "ollama status",
    "what local model is running",
    "is ollama running",
    "local llm status",
    "what model is loaded",
])
def test_ollama(msg):
    assert _detect_intent(msg) == "ollama"


# --- LLM Health ---

@pytest.mark.parametrize("msg", [
    "conversation health",
    "context health",
    "session health",
    "how's my conversation",
    "am i degrading",
    "chat health",
    "health score",
    "check conversation health",
    "my conversation health",
    "llm health",
    "conversation",
    "test chat health",
    "context quality",
])
def test_llm_health(msg):
    assert _detect_intent(msg) == "llm_health"


# --- Disk ---

@pytest.mark.parametrize("msg", [
    "disk usage",
    "how much storage do I have",
    "free up space",
    "what's taking space",
    "clean up disk",
    "large files",
    "gb free",
    "disk full",
    "clear cache",
])
def test_disk(msg):
    assert _detect_intent(msg) == "disk"


# --- Memory ---

@pytest.mark.parametrize("msg", [
    "memory usage",
    "how much ram",
    "out of memory",
    "memory leak",
    "swap usage",
    "available memory",
])
def test_memory(msg):
    assert _detect_intent(msg) == "memory"


# --- CPU ---

@pytest.mark.parametrize("msg", [
    "cpu usage",
    "processor load",
    "my computer is slow",
    "high load",
    "cpu hot",
    "fan noise",
])
def test_cpu(msg):
    assert _detect_intent(msg) == "cpu"


# --- Process ---

@pytest.mark.parametrize("msg", [
    "what's running",
    "top apps",
    "running processes",
    "what's open",
    "background processes",
    "kill process",
])
def test_process(msg):
    assert _detect_intent(msg) == "process"


# --- Health / system overview ---

@pytest.mark.parametrize("msg", [
    "how's my system",
    "system health",
    "health check",
    "system status",
    "overall health",
    "full scan",
    "how's my computer",
    "system check",
    "health",
    "status",
    "overview",
    "how is the system doing",
])
def test_health(msg):
    assert _detect_intent(msg) == "health"


# --- Social messages route to general fallback ---

@pytest.mark.parametrize("msg", [
    "hi",
    "hello",
    "hey",
    "good morning",
    "how are you",
    "thanks",
    "thank you",
    "who are you",
    "what are you",
    "meaning of life",
    "are you alive",
    "help",
    "what can you",
    "commands",
    "I feel lonely",
    "do you dream",
])
def test_social_messages_route_to_fallback(msg):
    assert _detect_intent(msg) == "general"


# --- General fallback ---

@pytest.mark.parametrize("msg", [
    "make me a sandwich",
    "the quick brown fox",
    "asdfghjkl",
    "42",
])
def test_general(msg):
    assert _detect_intent(msg) == "general"


# --- Priority ordering ---

def test_battery_not_general():
    """'battery' should be unsupported, not general."""
    assert _detect_intent("check battery") == "unsupported"


def test_empty_message():
    """Empty string returns 'general'."""
    assert _detect_intent("") == "general"
