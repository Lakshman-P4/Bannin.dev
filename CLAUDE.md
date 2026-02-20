# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Important — full project context**: This is the public-facing technical reference. The complete project documentation (strategy, roadmap, competitive context, engineering preferences, intelligence levels, phase details) lives at `../bannin-internal/CLAUDE.md`. Read that file at the start of every session for full context before doing any substantive work.

## Engineering Standards

Every line of code in this project must meet production-grade standards. No prototypes, no "clean up later."

**Code quality:**
- Production-ready on the first attempt. Complete, runnable, no placeholders or TODOs.
- Correctness first, then performance, then maintainability.
- Handle edge cases, errors, and validation comprehensively.
- Follow language-specific idioms strictly (Python: PEP 8, type hints; JS: ESLint conventions).
- DRY, SOLID, thread-safe, secure by default. Proper resource cleanup.
- Meaningful names that eliminate ambiguity. Minimal but essential comments — code should be self-documenting.
- No emojis in code or commit messages.

**Front-end caliber — Stripe, Linear, Vercel:**
- Cohesive, smooth, zero dead-end states.
- Every UI answers a question. Every interaction gives feedback. Every transition preserves context.
- The front-end/back-end seam is invisible to the user.

**Back-end caliber — Cloudflare, Stripe API discipline:**
- Clean pipelines, graceful degradation, full observability.
- Explicit, typed, idempotent. Built for the engineer debugging it at 2 AM.

**Problem-solving approach:**
1. Understand the core problem and constraints.
2. Choose optimal data structures and algorithms.
3. Implement the most efficient solution.
4. Validate against edge cases before delivering.

**Output expectations:**
- Immediately usable in production with minimal modification.
- Optimized for time and space complexity. Scalable under growth.
- Testable with clear interfaces. Secure against OWASP top 10.
- Would survive a code review at the best engineering org you can name.

**Communication:**
- Minimal explanation — let the code speak for itself.
- Only explain complex algorithms or non-obvious design decisions.
- No fluff, pure technical precision. Go straight to implementation.

## Project Overview

Bannin (番人, Japanese for "watchman") is a universal monitoring agent. It watches your machine, your LLMs, your cloud notebooks, and your coding tools — and surfaces health, alerts, and predictions through a local API, dashboard, and MCP server.

## Architecture

Five core components:

1. **Python Agent** (`bannin/`) — pip-installable package. Collects system metrics (CPU, RAM, GPU, disk) via `psutil`/`pynvml`, monitors LLM API usage, detects cloud notebook environments. Exposes REST API at `localhost:8420`.

2. **Relay Server** (Node.js, planned) — aggregates data from all agents, handles auth, stores history, dispatches push notifications.

3. **Phone App** (React Native, planned) — unified dashboard with live metrics, alerts, and action buttons.

4. **MCP Server** (`bannin/mcp/`) — Model Context Protocol server for AI coding tools (Claude Code, Cursor, Windsurf). Stdio transport, JSON-RPC 2.0.

5. **Browser Extension** (Chrome, planned) — monitors LLM web UIs (ChatGPT, Claude.ai, Gemini) for token estimation, latency, and conversation health.

```
User's Machine                              Cloud                    Mobile
+----------------------------------+
| Python Agent  <-->  MCP Server   |--WebSocket--> Relay Server <--Push--> Phone App
| (localhost:8420)                 |             (Node.js)              (React Native)
+----------------------------------+                 ^
                                                     |
Browser Extension ___________________________________/
(ChatGPT/Claude.ai/Gemini/Codex)
```

## Package Structure

```
bannin/
  __init__.py              # Exports: watch, wrap, track, Bannin, get_all_metrics
  api.py                   # FastAPI server (all endpoints)
  cli.py                   # CLI entry point (start/status/stop)
  dashboard.html           # Live monitoring dashboard
  config/
    loader.py              # Config loading logic
    defaults.json          # Default thresholds and alert rules
  core/
    collector.py           # psutil metrics collection
    gpu.py                 # NVIDIA GPU via pynvml
    process.py             # Process monitoring
    process_names.py       # Friendly process name mapping
  intelligence/
    alerts.py              # Threshold-based alert engine
    chat.py                # Rule-based chatbot (intent detection, data-driven responses)
    history.py             # Metric history ring buffer (2s intervals, 30min window)
    oom.py                 # OOM prediction (linear regression on memory trend)
    progress.py            # Training progress detection (tqdm hook, stdout regex)
    summary.py             # Plain-English system health summaries
  llm/
    health.py              # Conversation health scoring
    pricing.py             # Model pricing table (30+ models, 7 providers)
    tracker.py             # LLM call tracking (tokens, cost, latency)
    wrapper.py             # Client wrapper (OpenAI, Anthropic, Google, compatible)
  mcp/
    __init__.py
    __main__.py            # Entry point for python -m bannin.mcp
    server.py              # MCP tool definitions
  platforms/
    detector.py            # Environment detection (Colab, Kaggle, local)
    colab.py               # Google Colab monitoring
    kaggle.py              # Kaggle notebook monitoring
```

## API Endpoints (localhost:8420)

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Agent alive check |
| `/metrics` | GET | Full system snapshot (CPU, RAM, disk, network, GPU) |
| `/status` | GET | Agent identity (hostname, OS, version, uptime) |
| `/processes` | GET | Top processes with friendly names, categories, descriptions |
| `/summary` | GET | Plain-English system health summary |
| `/chat` | POST | Chatbot endpoint (natural language system health assistant) |
| `/alerts` | GET | Full alert history for this session |
| `/alerts/active` | GET | Currently active alerts |
| `/predictions/oom` | GET | OOM prediction with confidence and time-to-crash |
| `/history/memory` | GET | Memory usage history over last N minutes |
| `/tasks` | GET | Tracked tasks (training progress, ETAs) |
| `/tasks/{id}` | GET | Single task detail |
| `/llm/usage` | GET | LLM session health and usage summary |
| `/llm/calls` | GET | Recent LLM API call history |
| `/llm/context` | GET | Context window exhaustion prediction |
| `/llm/latency` | GET | Response latency trend analysis |
| `/platform` | GET | Cloud notebook platform info (Colab/Kaggle) |

## MCP Tools

| Tool | Purpose |
|---|---|
| `get_system_metrics` | Full system snapshot (CPU, RAM, disk, network, GPU) |
| `get_running_processes` | Top processes by CPU/memory with friendly names |
| `predict_oom` | Memory exhaustion prediction with confidence |
| `get_training_status` | Tracked task progress and ETAs |
| `get_active_alerts` | Current monitoring alerts |

## Key Dependencies

- `psutil` — CPU, RAM, disk, network
- `pynvml` — NVIDIA GPU (optional)
- `fastapi` + `uvicorn` — local API server
- `mcp` (Anthropic SDK) — MCP server (optional)
- `click` — CLI

## Cross-Platform

| Feature | macOS (Apple Si) | Windows/Linux |
|---|---|---|
| CPU/RAM/Disk | psutil | psutil |
| GPU | macmon (planned) | pynvml (NVIDIA) |
| Process mgmt | psutil + signal | psutil + signal |

## Dashboard Features

- **Live metrics**: CPU, RAM, Disk, GPU gauges with color-coded bars (cyan/amber/red)
- **Visual urgency**: Metric cards glow amber at 60% usage, pulse red at 80%+
- **Process table**: Top 8 processes with friendly names, category badges, hover tooltips (2s delay) explaining what each process is and why multi-instance counts are normal
- **Memory trend chart**: 5-minute rolling Chart.js graph
- **OOM prediction**: Real-time memory crash prediction with confidence scores
- **Alerts banner**: Active alerts with severity indicators
- **Plain-English summary**: One-click system health summary with suggestions
- **Chatbot ("Ask Bannin")**: Inline chat with intent detection, data-driven responses, 1.8s typing delay with eye-blink animation. Handles system health questions, disk/RAM/CPU analysis, off-topic/social messages
- **Loading eye animation**: Bannin eye opens when data is ready
- **Glassmorphism design**: Near-black palette, backdrop blur, gradient border reveals on hover

## Other Files

- `feedback.html` — Trial feedback form (12 questions, Phase 1 & 2). Submits to Google Sheets via Apps Script.
- `trial.md` / `trial-colab.md` / `trial-vscode.md` / `trial-powershell.md` — Platform-specific trial guides.

## Known Issues

- **Windows PATH**: CLI may not be on PATH after `pip install --user`. Use `python -m bannin.cli start`.
- **Port conflict**: Starting agent twice causes port 8420 conflict. Agent detects and warns.
