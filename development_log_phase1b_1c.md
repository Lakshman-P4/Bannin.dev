# Vigilo Development Log

---

# Phase 1b — Cloud Notebook Monitoring (Colab & Kaggle)

**Date**: [DATE]
**Goal**: Detect whether Vigilo is running inside a cloud notebook environment and activate platform-specific monitoring for Colab and Kaggle constraints.
**Status**: IN PROGRESS — Researching platform constraints
**Depends on**: Phase 1a (Python Agent Core) ✅

---

## What Needs to Be Built

Vigilo's Python agent needs to detect its runtime environment and activate specialized monitoring. The same `pip install vigilo` command works everywhere, but the agent should behave differently inside Colab vs. Kaggle vs. a local machine.

### Components to Create

| File | What It Does | Plain English |
|---|---|---|
| `vigilo/platforms/__init__.py` | Platform module init | Makes platform detection importable |
| `vigilo/platforms/detect.py` | Environment detection | Answers: "Am I in Colab, Kaggle, or local?" |
| `vigilo/platforms/colab.py` | Colab-specific monitor | Tracks session time, GPU type, VRAM, ephemeral storage |
| `vigilo/platforms/kaggle.py` | Kaggle-specific monitor | Tracks GPU quota, session limits, output size, internet access |
| `vigilo/platforms/checkpoint.py` | Auto-checkpoint engine | Saves model state to Google Drive before session death |

### API Endpoints to Add/Modify

| Endpoint | Change | Purpose |
|---|---|---|
| `GET /status` | Add `platform` field | Reports "colab", "kaggle", or "local" |
| `GET /metrics` | Add platform-specific fields | Session time remaining, GPU quota, etc. |
| `GET /tasks` | Enhance with notebook context | Show notebook session as a monitored task |

---

## Research Notes

### Environment Detection Strategy

**How to detect Colab:**
- [ ] Check for `google.colab` module: `importlib.util.find_spec("google.colab")`
- [ ] Check for Colab-specific env vars (e.g., `COLAB_GPU`, `COLAB_RELEASE_TAG`)
- [ ] Check filesystem markers (e.g., `/content/` directory)
- [ ] Document findings here: [FINDINGS]

**How to detect Kaggle:**
- [ ] Check for `KAGGLE_KERNEL_RUN_TYPE` environment variable
- [ ] Check for `KAGGLE_DATA_PROXY_TOKEN` environment variable
- [ ] Check filesystem markers (e.g., `/kaggle/` directory)
- [ ] Document findings here: [FINDINGS]

### Colab Constraints Research

| Constraint | How to Detect | How to Monitor | Research Status |
|---|---|---|---|
| Session time (~12hr max) | Track elapsed time from agent start | Compare against known limits | [ ] TODO |
| Idle timeout (~90min) | Detect user activity / heartbeat | Warn before idle disconnect | [ ] TODO |
| GPU type | `!nvidia-smi` or pynvml `nvmlDeviceGetName()` | Poll periodically, detect changes | [ ] TODO |
| GPU reallocation | GPU name changes between polls | Compare current vs. previous GPU type | [ ] TODO |
| VRAM limits | pynvml `nvmlDeviceGetMemoryInfo()` | Track usage, predict OOM against hard limit | [ ] TODO |
| Ephemeral storage | `psutil.disk_usage('/content/')` | Monitor, trigger checkpoint at threshold | [ ] TODO |
| Runtime restart | Agent process dying / PID change | Detect via heartbeat loss | [ ] TODO |
| Google Drive mount | Check if `/content/drive/` exists | Needed for auto-checkpoint destination | [ ] TODO |

### Kaggle Constraints Research

| Constraint | How to Detect | How to Monitor | Research Status |
|---|---|---|---|
| Weekly GPU quota (~30hrs) | Kaggle API or manual tracking | Cumulative session time tracking | [ ] TODO |
| Session time (12hr CPU, 9hr GPU) | Track elapsed time | Countdown, warn before timeout | [ ] TODO |
| Internet access | Try socket connection or check env var | Warn if disabled and code needs internet | [ ] TODO |
| Output storage (~20GB) | `du -sh /kaggle/working/` | Monitor size, warn at threshold | [ ] TODO |
| Accelerator type | `torch.cuda.get_device_name()` or env var | Detect GPU/TPU type and changes | [ ] TODO |

---

## Implementation Log

### [DATE] — [WHAT WAS DONE]

[Write implementation notes here as you build, following the Phase 1a format]

---

## Challenges & Errors

### Challenge 1: [TITLE]

**What happened:**
**Why:**
**Fix:**
**Impact on users:**

---

## Test Results

### Colab Test — [DATE]

[Paste test results from running in Colab here]

### Kaggle Test — [DATE]

[Paste test results from running in Kaggle here]

---

## Phase 1b Completion Checklist

| Feature | Status | Notes |
|---|---|---|
| Environment detection (is_colab, is_kaggle, is_local) | [ ] | |
| Colab session time tracking | [ ] | |
| Colab GPU type detection + reallocation alert | [ ] | |
| Colab VRAM monitoring + OOM prediction | [ ] | |
| Colab ephemeral storage monitoring | [ ] | |
| Kaggle GPU quota tracking | [ ] | |
| Kaggle session countdown | [ ] | |
| Kaggle output size monitoring | [ ] | |
| Auto-checkpoint to Google Drive | [ ] | |
| `/status` endpoint updated with platform field | [ ] | |
| `/metrics` endpoint updated with platform fields | [ ] | |
| Tested in real Colab notebook | [ ] | |
| Tested in real Kaggle notebook | [ ] | |

**Phase 1b proves**: Vigilo works not just on your laptop but inside the cloud notebook environments where students and ML engineers actually train models. The same `pip install vigilo` gives you platform-aware monitoring everywhere.

---

*Next: Phase 1c — LLM API Middleware*

---
---

# Phase 1c — LLM API Middleware

**Date**: [DATE]
**Goal**: Build a Python middleware that wraps LLM API calls (OpenAI, Anthropic, Google) to track token usage, cost, latency, and context window health — and detect conversation depreciation.
**Status**: NOT STARTED
**Depends on**: Phase 1a (Python Agent Core) ✅, Phase 1b (Cloud Notebooks) ideally complete but not blocking

---

## What Needs to Be Built

A transparent wrapper around LLM API clients that intercepts completions, extracts usage metadata, and feeds it into Vigilo's monitoring pipeline. This is the foundation for LLM-as-infrastructure monitoring and the conversation depreciation feature.

### Components to Create

| File | What It Does | Plain English |
|---|---|---|
| `vigilo/llm/__init__.py` | LLM module init | Makes LLM tracking importable |
| `vigilo/llm/wrapper.py` | Client wrapper | `vigilo.wrap(OpenAI())` — intercepts all API calls transparently |
| `vigilo/llm/tracker.py` | Usage tracker | Accumulates tokens, cost, latency per conversation/session |
| `vigilo/llm/pricing.py` | Model pricing table | Maps model names to per-token costs (maintained/updatable) |
| `vigilo/llm/health.py` | Conversation health | Detects context window exhaustion, latency degradation, depreciation |
| `vigilo/llm/context_transfer.py` | Context summarizer | Generates compressed context summary for new conversation injection |

### API Endpoints to Add

| Endpoint | Method | Purpose |
|---|---|---|
| `GET /llm/usage` | GET | Current session LLM usage (tokens, cost, calls) |
| `GET /llm/conversations` | GET | List of tracked conversations with health scores |
| `GET /llm/cost` | GET | Daily/weekly cost summary across providers |
| `GET /llm/health/{conversation_id}` | GET | Health score for a specific conversation |

### Developer-Facing API

Two integration patterns (both under 3 lines of code):

```python
# Pattern 1: Context manager
import vigilo

with vigilo.track():
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}]
    )

# Pattern 2: Wrapped client
import vigilo
from openai import OpenAI

client = vigilo.wrap(OpenAI())
# All subsequent calls are automatically tracked
response = client.chat.completions.create(...)
```

---

## Data Collected Per API Call

| Metric | Source | Use |
|---|---|---|
| Input tokens | `response.usage.prompt_tokens` | Cost calculation, context tracking |
| Output tokens | `response.usage.completion_tokens` | Cost calculation |
| Cached tokens | `response.usage.prompt_tokens_details.cached_tokens` | Cost optimization insight |
| Model name | `response.model` | Pricing lookup |
| Latency (ms) | Time between request sent and first byte received | Degradation detection |
| Cost ($) | Calculated: tokens × model price from pricing table | Spend alerts, daily summaries |
| Context window used (%) | Cumulative tokens / model's max context | Exhaustion prediction |
| Conversation ID | User-assigned or auto-generated | Per-conversation tracking |

## Conversation Depreciation Detection

**What it detects:**
- Context window filling up (e.g., "87K of 128K tokens used — ~3 messages left")
- Latency trending upward (response times climbing across consecutive calls)
- Cost per message increasing (more tokens needed per exchange as context grows)

**What it recommends:**
- "This conversation is degrading. Consider starting fresh."
- "Context window 90% full. Summary available for transfer."

**Context transfer (early version):**
- When triggered, generates a compressed summary of the conversation state
- Summary captures: key decisions made, current task in progress, important facts established, user preferences expressed
- Summary can be injected as a system message in a new conversation
- The user gets a fast, fresh conversation that retains the important context

---

## Supported Providers

| Provider | Client Object | Token Source | Pricing |
|---|---|---|---|
| OpenAI | `openai.OpenAI()` | `response.usage` | Per-model from pricing table |
| Anthropic | `anthropic.Anthropic()` | `response.usage` | Per-model from pricing table |
| Google | `google.generativeai` | `response.usage_metadata` | Per-model from pricing table |

### Model Pricing Table (to maintain)

```python
# vigilo/llm/pricing.py — sample structure
MODEL_PRICES = {
    "gpt-4o": {"input": 2.50, "output": 10.00},           # per 1M tokens
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-haiku-3-5-20241022": {"input": 0.80, "output": 4.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    # ... extend as needed
}
```

This table needs to be updatable (load from config file or fetch from a maintained source).

---

## Implementation Log

### [DATE] — [WHAT WAS DONE]

[Write implementation notes here as you build]

---

## Challenges & Errors

### Challenge 1: [TITLE]

**What happened:**
**Why:**
**Fix:**
**Impact on users:**

---

## Test Results

### OpenAI Wrapper Test — [DATE]

[Test with real OpenAI API call, paste response + tracked metrics]

### Anthropic Wrapper Test — [DATE]

[Test with real Anthropic API call, paste response + tracked metrics]

### Context Window Exhaustion Test — [DATE]

[Test with a long conversation, verify exhaustion prediction accuracy]

---

## Phase 1c Completion Checklist

| Feature | Status | Notes |
|---|---|---|
| vigilo.wrap() for OpenAI client | [ ] | |
| vigilo.wrap() for Anthropic client | [ ] | |
| vigilo.wrap() for Google client | [ ] | |
| vigilo.track() context manager | [ ] | |
| Token counting per call | [ ] | |
| Cost calculation per call | [ ] | |
| Model pricing table (maintained) | [ ] | |
| Cumulative session tracking | [ ] | |
| Context window exhaustion prediction | [ ] | |
| Latency degradation detection | [ ] | |
| Spend alerting (threshold-based) | [ ] | |
| Conversation health scoring | [ ] | |
| Context summary generation | [ ] | |
| `/llm/usage` endpoint | [ ] | |
| `/llm/conversations` endpoint | [ ] | |
| `/llm/cost` endpoint | [ ] | |
| Tested with real OpenAI calls | [ ] | |
| Tested with real Anthropic calls | [ ] | |

**Phase 1c proves**: Vigilo monitors not just your hardware but your LLM spend and conversation health. The same platform that tells you "RAM at 92%" also tells you "you've spent $4.20 today" and "this conversation is degrading — start fresh with context transfer."

---

*Next: Phase 2 — Intelligence Engine (OOM prediction, progress detection, threshold alerts)*
