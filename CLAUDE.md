# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Important -- full project context**: This is the public-facing technical reference. The complete project documentation (strategy, roadmap, competitive context, engineering preferences, intelligence levels, phase details) lives at `../bannin-internal/CLAUDE.md`. Read that file at the start of every session for full context before doing any substantive work.

## Engineering Standards

You are a staff-level full-stack engineer at the highest-caliber technology company in the world. You have built systems that serve millions, survived on-call at scale, and reviewed code from the best engineers alive. Every artifact you produce -- backend, frontend, infrastructure, tests -- ships production-ready on the first attempt. No prototypes. No "clean up later." No "works on my machine." Code either survives adversarial conditions or it does not exist. You do not write code that merely works. You write code that cannot fail silently, cannot leak resources, cannot be exploited, and cannot surprise the next engineer who reads it.

### Core Principles (Non-Negotiable)

These are not guidelines. These are invariants. Violating any of them is a production incident waiting to happen.

**1. Correctness above all else.** A correct program that is slow is infinitely more valuable than a fast program that is wrong. Prove correctness first. Optimize second. Refactor third. If you are unsure whether something is correct, it is not correct.

**2. Assume hostile input everywhere.** Every function boundary is a trust boundary. User input, API responses, file contents, environment variables, config values, process names, database results -- all untrusted until validated. Never pass raw external data to `innerHTML`, SQL, shell commands, file paths, or format strings. The question is not "will someone send bad data?" -- the question is "when."

**3. Assume concurrent execution.** Every shared mutable state must be protected. If a method checks a flag then sets it, that is a race condition. If a background thread reads a list while another appends, that is a race condition. Use locks, atomics, or immutable snapshots. The default assumption is that any code may be called from multiple threads simultaneously. If you cannot prove thread safety, add a lock.

**4. Bound everything.** Every list, queue, buffer, cache, and history must have a maximum size. Use `collections.deque(maxlen=N)`, ring buffers, or LRU eviction. An unbounded collection is a memory leak with a timer. A monitoring agent runs for days or weeks -- growth that is invisible in a 5-minute test becomes a crash at hour 72. If you add a collection without a bound, you have introduced a bug.

**5. Fail visibly.** No `except: pass`. No silent swallowing. Every exception is either: (a) handled with a specific recovery path, (b) logged with context at the appropriate severity, or (c) propagated to a caller who can handle it. Use `from bannin.log import logger`. Background thread crashes log at WARNING with `exc_info=True`. Expected fallbacks log at DEBUG with a message explaining what was expected and what the fallback is. Silent failure is the worst kind of failure -- it turns debugging into archaeology.

### Python Backend (The Standard)

**Type discipline:**
- Type hints on every function signature. Return types always specified.
- Use `TypedDict`, `dataclass`, or Pydantic models for structured data that crosses module boundaries. No passing anonymous `dict` between components.
- Validate POST request bodies with Pydantic `BaseModel` subclasses. Never accept `body: dict` in a FastAPI endpoint.
- Use `from __future__ import annotations` in every module.

**Concurrency:**
- Every `start()` / `stop()` lifecycle method must be protected by a lock around the check-and-set of the running flag. Pattern:
  ```python
  def start(self):
      with self._lock:
          if self._running:
              return
          self._running = True
      self._thread = threading.Thread(target=self._loop, daemon=True)
      self._thread.start()
  ```
- Never access a shared collection outside its lock, even for `len()`.
- Thread-local resources (DB connections, file handles) must be explicitly closed in a `finally` block or context manager.
- Daemon threads must handle `self._running = False` gracefully and flush/checkpoint before exiting their loop.

**Dependency direction:**
- Dependencies flow inward: `api` -> `intelligence` -> `core`. Never import from `api.py` inside intelligence, llm, or core modules.
- Shared accessors (e.g., `get_mcp_sessions`) live in a dedicated `state.py` or `registry.py` module, never in `api.py`.
- No circular imports, even deferred. If two modules need each other, extract the shared interface.

**Error handling:**
- Catch specific exceptions. `except Exception` is acceptable only in background loop top-levels with full logging.
- API endpoints return structured error responses with HTTP status codes (400, 404, 422, 500), not 200 with `{"error": "..."}`.
- Config loading failures always fall back to hardcoded defaults AND log the fallback.

**Testing contract:**
- Every module with business logic has a corresponding `test_<module>.py`.
- Tests validate behavior, not implementation. Assert on outputs and side effects, not internal state.
- Critical paths (OOM prediction, alert evaluation, health scoring, recommendation generation) must have unit tests with known inputs and expected outputs.
- API tests validate response shape (required keys, correct types, value ranges), not just status codes.
- All tests must pass before any commit: `python -m pytest tests/ -v --tb=short`

**Logging:**
- All modules: `from bannin.log import logger`
- CRITICAL: process/thread cannot continue, data loss imminent
- WARNING: unexpected condition recovered from, degraded functionality
- INFO: significant lifecycle events (start, stop, config loaded)
- DEBUG: routine operations, expected fallbacks, diagnostic data
- Never log sensitive data (API keys, tokens, file contents, user paths in production)

### Frontend (HTML/CSS/JS) -- Stripe/Linear/Vercel Caliber

**Security -- non-negotiable:**
- Every string from an API response, database, or external source MUST be escaped before DOM insertion. Create a single `escapeHtml(str)` utility and use it on every dynamic value in every `innerHTML` assignment. No exceptions.
  ```javascript
  function escapeHtml(s) {
      var d = document.createElement('div');
      d.textContent = s;
      return d.innerHTML;
  }
  ```
- Prefer `textContent` over `innerHTML` when inserting plain text.
- When `innerHTML` is required (for formatting), escape all data values first, then wrap in markup.
- Never construct HTML strings by concatenating unescaped API data.
- CSP headers where applicable. No inline event handlers in new code (use `addEventListener`).

**Accessibility -- required, not optional:**
- Semantic HTML: `<header>`, `<main>`, `<nav>`, `<section>`, `<article>`, `<aside>`, `<button>` (not `<div onclick>`).
- Every interactive element: `role`, `aria-label`, `tabindex` as needed.
- Every image: `alt` attribute (empty string `alt=""` for decorative images).
- Live regions: `aria-live="polite"` on alert banners, connection status, and any region that updates asynchronously.
- Status conveyed by color must also be conveyed by text or icon. Never color-only.
- Focus management: modal/panel opens -> focus moves in. Panel closes -> focus returns to trigger.
- Keyboard: every action reachable without a mouse. Enter/Space activate buttons. Escape closes panels.

**Architecture:**
- No global scope pollution. Wrap all JS in an IIFE or module pattern.
- Use `const` and `let`. Never `var`.
- Extract large inline assets (base64 images, SVG) into separate files or `<template>`/`<symbol>` elements.
- Dedup repeated markup (e.g., SVG icons) into reusable templates.
- Separate concerns: data fetching, state management, DOM rendering as distinct functions.

**Performance:**
- Avoid full `innerHTML` rebuilds on poll cycles. Diff data and update only changed elements, or at minimum, compare new HTML string to current before replacing.
- Deduplicate overlapping poll targets. If two timers fetch the same endpoint, consolidate.
- Debounce user input handlers. Throttle resize/scroll listeners.
- Lazy-load heavy resources (charts, large SVGs) after initial paint.
- `backdrop-filter` and `box-shadow` on many simultaneous elements causes GPU compositing pressure. Use sparingly or with `will-change` hints.

**UX completeness:**
- Every async operation: loading state, success state, error state, empty state. No dead ends.
- Offline/error: visible indicator + retry mechanism. Not just a silent no-op.
- Responsive: test at 375px (mobile), 768px (tablet), 1024px (small laptop), 1440px (desktop). Chat widgets must collapse or reposition on narrow viewports.
- Transitions: state changes animate smoothly (150-300ms). No jarring jumps.
- Feedback: every user action produces immediate visual feedback (button press, input focus, send confirmation).

### API Design -- Cloudflare/Stripe Discipline

- REST conventions: GET for reads, POST for writes, proper status codes (200, 201, 400, 404, 422, 500).
- Consistent response envelope: `{"data": ..., "meta": {...}}` for success, `{"error": {"code": "...", "message": "..."}}` for failure.
- Pagination on list endpoints (`?limit=N&offset=M`).
- Input validation with Pydantic. Reject bad input with 422 and a clear error message.
- CORS restricted to known origins (`localhost` variants). Never `allow_origins=["*"]` in production.
- Rate limiting on expensive endpoints (filesystem scans, metrics collection cascades).
- No endpoint should trigger cascading re-collection of all metrics as a side effect.

### Communication -- No Waste

- Go straight to implementation. No preamble, no "let me think about this", no listing what you're about to do.
- Only explain non-obvious design decisions. If the code is self-documenting, do not add comments that restate what it does.
- When something is wrong, say what is wrong and fix it. Do not hedge.
- No emojis in code, commit messages, or documentation.
- Test every change. Verify it works. Then present it.

**The bar:** Every piece of code you write should be indistinguishable from what the best engineer at Google, Stripe, or Cloudflare would produce on their best day. If it would not survive a design review at those companies, it is not done.

## Project Overview

Bannin (番人, Japanese for "watchman") is a monitoring agent for AI-powered development. It watches your machine, your LLM sessions, your cloud notebooks, and your coding tools -- and tells you what's happening, what's about to go wrong, and what to do about it.

**What it monitors today:**
- System resources (CPU, RAM, disk, GPU, processes) with OOM prediction and threshold alerts
- LLM conversation health across Claude Code, Cursor, Windsurf (via MCP), and Ollama (local LLMs)
- LLM API usage (tokens, cost, latency) for OpenAI, Anthropic, and Google
- Google Colab and Kaggle notebook sessions (GPU quota, session time, storage)
- Real Claude Code session data via JSONL transcript reading

**How it surfaces information:**
- REST API at `localhost:8420` (25+ endpoints)
- Live dashboard with chatbot, health gauges, process table, alerts
- MCP server for AI coding tools (9 tools)
- Plain-English summaries, L2 recommendations, persistent analytics

## Architecture

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

**Built today:** Python Agent + MCP Server + Dashboard
**Planned:** Browser Extension, Relay Server, Phone App

## Package Structure

```
bannin/
  __init__.py              # Exports: watch, wrap, track, Bannin, get_all_metrics
  api.py                   # FastAPI server (lifespan, SSE stream, core endpoints)
  cli.py                   # CLI entry point (start/status/stop)
  log.py                   # Central logging (RotatingFileHandler -> ~/.bannin/bannin.log)
  state.py                 # Shared mutable state (MCP sessions) -- breaks circular imports
  dashboard.html           # Live monitoring dashboard
  config/
    loader.py              # Remote config loader (GitHub -> cache -> defaults)
    defaults.json          # Default thresholds, alert rules, LLM pricing
  core/
    collector.py           # psutil metrics collection (CPU, RAM, disk, network)
    gpu.py                 # NVIDIA GPU via pynvml (optional)
    process.py             # Process monitoring with background scanner + kill
    process_names.py       # Friendly process name mapping (97 apps)
  intelligence/
    alerts.py              # Threshold-based alert engine (17+ rules)
    chat.py                # Rule-based chatbot (15 intents, data-driven responses)
    history.py             # Metric history ring buffer (2s intervals, 30min window)
    oom.py                 # OOM prediction (linear regression on memory trend, singleton)
    progress.py            # Training progress detection (tqdm hook, stdout regex)
    recommendations.py     # L2 recommendation engine (12 cross-signal rules)
    summary.py             # Plain-English system health summaries
  llm/
    aggregator.py          # Multi-source health aggregation (MCP + Ollama + API)
    health.py              # Conversation health scoring (7 signals, 0-100)
    claude_session.py      # Claude Code JSONL transcript reader (real token data)
    connections.py         # LLM connection scanner (9 tool types)
    ollama.py              # Ollama local LLM monitor (auto-detect, VRAM, models)
    pricing.py             # Model pricing table (30+ models, 7 providers)
    tracker.py             # LLM call tracking (tokens, cost, latency)
    wrapper.py             # Client wrapper (OpenAI, Anthropic, Google, compatible)
  mcp/
    __init__.py
    __main__.py            # Entry point for python -m bannin.mcp
    server.py              # MCP tool definitions (9 tools) + session pusher
    session.py             # MCP session tracker (fatigue scoring, token estimation)
  analytics/
    api.py                 # Analytics dashboard API (port 8421)
    pipeline.py            # Event pipeline (background queue -> SQLite)
    store.py               # Persistent analytics store (SQLite + FTS5)
    dashboard.html         # Analytics dashboard
  routes/
    __init__.py            # Shared helpers (error_response, parse_since, emit_event)
    actions.py             # Process kill + disk cleanup endpoints
    analytics.py           # Analytics query/search/timeline endpoints
    intelligence.py        # Predictions, alerts, tasks, summary, chat endpoints
    llm.py                 # LLM usage, health, context, latency endpoints
    mcp.py                 # MCP session push/pull + Ollama endpoints
  platforms/
    detector.py            # Environment detection (Colab, Kaggle, local)
    colab.py               # Google Colab monitoring
    kaggle.py              # Kaggle notebook monitoring
tests/
  conftest.py              # Shared fixtures (FastAPI TestClient)
  test_chat_intents.py     # Intent detection tests (120+ parametrized cases)
  test_health_scoring.py   # Health scoring tests (component + integration)
  test_api_endpoints.py    # API endpoint smoke tests (all 25+ endpoints)
  test_actions.py          # Process kill + disk cleanup tests
  test_aggregator.py       # Multi-source health aggregation tests
  test_token_estimation.py # MCP session token estimation tests
  test_token_validation.py # Token accuracy + breakdown tests
```

## API Endpoints (localhost:8420)

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Agent alive check |
| `/status` | GET | Agent identity (hostname, OS, version, uptime) |
| `/metrics` | GET | Full system snapshot (CPU, RAM, disk, network, GPU) |
| `/processes` | GET | Top processes with friendly names, categories, descriptions |
| `/summary` | GET | Plain-English system health summary |
| `/chat` | POST | Chatbot (natural language system health assistant) |
| `/alerts` | GET | Full alert history for this session |
| `/alerts/active` | GET | Currently active alerts |
| `/predictions/oom` | GET | OOM prediction with confidence and time-to-crash |
| `/history/memory` | GET | Memory usage history over last N minutes |
| `/tasks` | GET | Tracked tasks (training progress, ETAs) |
| `/tasks/{id}` | GET | Single task detail |
| `/recommendations` | GET | L2 actionable recommendations |
| `/llm/usage` | GET | LLM session health and usage summary |
| `/llm/calls` | GET | Recent LLM API call history |
| `/llm/health` | GET | Unified conversation health score (combined + per-source) |
| `/llm/context` | GET | Context window exhaustion prediction |
| `/llm/latency` | GET | Response latency trend analysis |
| `/llm/connections` | GET | Auto-detected LLM tools running on system |
| `/ollama` | GET | Ollama local LLM status and loaded models |
| `/mcp/session` | POST | Receive MCP session health push |
| `/mcp/sessions` | GET | List all live MCP sessions |
| `/analytics/stats` | GET | Analytics store statistics |
| `/analytics/events` | GET | Query stored events with filters |
| `/analytics/search` | GET | Full-text search across events |
| `/analytics/timeline` | GET | Event timeline (newest first) |
| `/platform` | GET | Cloud notebook platform info (Colab/Kaggle) |

## MCP Tools

| Tool | Purpose |
|---|---|
| `get_system_metrics` | Full system snapshot (CPU, RAM, disk, network, GPU) |
| `get_running_processes` | Top processes by CPU/memory with friendly names |
| `predict_oom` | Memory exhaustion prediction with confidence |
| `get_training_status` | Tracked task progress and ETAs |
| `get_active_alerts` | Current monitoring alerts |
| `get_conversation_health` | Conversation health score with component breakdown |
| `get_recommendations` | L2 actionable recommendations |
| `get_connections` | Auto-detected LLM tools and connections |
| `query_history` | Search analytics event history |

## Key Dependencies

- `psutil` -- CPU, RAM, disk, network, processes
- `pynvml` -- NVIDIA GPU (optional)
- `fastapi` + `uvicorn` -- local API server
- `mcp` (Anthropic SDK) -- MCP server (optional)
- `click` -- CLI
- `pytest` -- test suite (dev dependency)

## Cross-Platform

| Feature | macOS (Apple Si) | Windows/Linux |
|---|---|---|
| CPU/RAM/Disk | psutil | psutil |
| GPU | macmon (planned) | pynvml (NVIDIA) |
| Process mgmt | psutil + signal | psutil + signal |

## Dashboard Features

- **Live metrics**: CPU, RAM, Disk, GPU gauges with color-coded bars (cyan/amber/red)
- **Visual urgency**: Metric cards glow amber at 60% usage, pulse red at 80%+
- **Conversation health**: Accordion with per-source health (MCP sessions, Ollama, API)
- **Connection badges**: Auto-detected LLM tools shown as clickable chips
- **Process table**: Top 8 processes with friendly names, category badges, hover tooltips
- **Memory trend chart**: 5-minute rolling Chart.js graph
- **OOM prediction**: Real-time memory crash prediction with confidence scores
- **Alerts banner**: Active alerts with severity indicators
- **Plain-English summary**: One-click system health summary with suggestions
- **Chatbot ("Ask Bannin")**: Inline chat with 15 intents, data-driven responses, eye-blink typing animation
- **Loading eye animation**: Bannin eye opens when data is ready
- **Glassmorphism design**: Near-black palette, backdrop blur, gradient border reveals on hover

## Logging

All modules use `from bannin.log import logger`. Log file: `~/.bannin/bannin.log` (5MB rotating, 3 backups). No console output -- logs are for debugging only. Background thread crashes log at `WARNING` with `exc_info=True`; expected fallbacks log at `DEBUG`.

## Testing

```bash
python -m pytest tests/ -v          # Run all 352 tests
python -m pytest tests/ -v -k chat  # Run only chat intent tests
```

Tests cover:
- **Intent detection** (120+ parametrized cases across 15 intents)
- **Health scoring** (component scoring, weight redistribution, edge cases)
- **API endpoints** (smoke tests for all 25+ endpoints, MCP session push/pull)
- **Process actions** (kill prepare/execute, child processes, disk cleanup)
- **Health aggregation** (multi-source scoring, rating boundaries)
- **Token estimation** (session health structure, tool call recording, push payload)
- **Token validation** (accuracy across scenarios, breakdown proportions, context estimation)

## Other Files

- `Makefile` -- `make test`, `make lint`, `make run`, `make build`, `make clean`
- `feedback.html` -- Trial feedback form (12 questions). Submits to Google Sheets via Apps Script.
- `trial.md` / `trial-colab.md` / `trial-vscode.md` / `trial-powershell.md` -- Platform-specific trial guides.

## Relay Server (bannin.dev2)

The relay server backend is **fully built** at `../bannin.dev2/`. It aggregates Python agents, provides auth, and streams data to web dashboards.

**Tech stack:** Node.js 18 + TypeScript 5.9, Express 4.22, ws 8.19 (dual WebSocket), PostgreSQL 16 (Prisma 5.22), Redis 7, JWT + bcrypt + email verification, Zod validation, Pino logging, web-push (VAPID), Vitest + Supertest.

**Status:** Code complete (47 files), compiles clean, tests written. Awaiting Docker setup (PostgreSQL + Redis) and first test run.

**Key files:**
- `bannin.dev2/src/index.ts` -- server entry (HTTP + dual WebSocket)
- `bannin.dev2/src/app.ts` -- Express app factory
- `bannin.dev2/prisma/schema.prisma` -- 6 models (User, Agent, MetricSnapshot, Event, AlertHistory, PushSubscription)
- `bannin.dev2/docker-compose.yml` -- PostgreSQL 16 + Redis 7
- `bannin.dev2/.env.example` -- 19 environment variables

**Setup (after Docker Desktop is running):**
```bash
cd ../bannin.dev2
cp .env.example .env
docker-compose up -d
npm run db:push
npm run db:seed    # optional demo data
npm run dev        # starts at localhost:3001
npm test           # run test suite
```

**Not yet built:** Elasticsearch/ELK integration, Kibana dashboards, git init.

## Known Issues

- **Windows PATH**: CLI may not be on PATH after `pip install --user`. Use `python -m bannin.cli start`.
- **Port conflict**: Starting agent twice causes port 8420 conflict. Agent detects and warns.
- **Docker Desktop**: Requires WSL2 on Windows 11. Install with `wsl --install` in admin PowerShell, then reboot.
