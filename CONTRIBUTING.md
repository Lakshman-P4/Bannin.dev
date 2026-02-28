# Contributing to Bannin

Bannin is a universal monitoring agent for AI-powered development. This guide covers everything you need to start contributing.

## Architecture

```
bannin/
  api.py                   # FastAPI app, core endpoints, SSE stream
  routes/                  # Sub-routers (llm, intelligence, mcp, analytics)
  core/                    # System metrics (psutil), process scanner, GPU
  intelligence/            # Alerts, OOM prediction, chatbot, recommendations
  llm/                     # LLM tracking, health scoring, Ollama, aggregator
  mcp/                     # MCP server for AI coding tools
  analytics/               # Event pipeline + SQLite persistence
  platforms/               # Colab/Kaggle detection
  config/                  # Remote config loader + defaults.json
  state.py                 # Shared mutable state (MCP sessions)
  log.py                   # Central logger (RotatingFileHandler)
  dashboard.html           # Live monitoring dashboard
tests/                     # pytest suite (352 tests)
```

**Dependency direction:** `api` -> `routes` -> `intelligence`/`llm` -> `core`. Never import from `api.py` inside intelligence, llm, or core.

## Dev Setup

```bash
# Clone and install (editable mode)
git clone https://github.com/Lakshman-P4/Bannin.dev.git
cd Bannin.dev
pip install --user -e .

# Start the agent
python -m bannin.cli start

# Open dashboard
# http://localhost:8420
```

**Windows note:** Use `python -m bannin.cli start` since `bannin.exe` may not be on PATH.

**macOS note:** Use `python3` instead of `python`.

## Testing

```bash
# Run full suite
python -m pytest tests/ -v --tb=short

# Run specific test file
python -m pytest tests/test_chat_intents.py -v

# Run tests matching a keyword
python -m pytest tests/ -v -k "health"
```

All tests must pass before any commit. The suite covers:
- Intent detection (120+ parametrized cases)
- Health scoring (component + integration)
- API endpoints (smoke tests for all 25+ endpoints)
- Alert engine, OOM prediction, token estimation
- LLM wrapper, aggregator

## Code Style

### Python
- Type hints on every function signature. Return types always specified.
- `from __future__ import annotations` in every module.
- Logging: `from bannin.log import logger`. No `print()` statements.
- Threading: protect shared state with locks. See `state.py` for the pattern.
- Bound every collection: `collections.deque(maxlen=N)` or similar.
- No `except: pass`. Log or handle every exception.
- Catch specific exceptions. `except Exception` only in background loop top-levels.

### Frontend (dashboard.html)
- Escape all API data before DOM insertion via `escapeHtml()`.
- Semantic HTML, ARIA attributes, keyboard accessibility.
- No `var` -- use `const` and `let`.
- No global scope pollution -- wrap in IIFE or module pattern.

### API
- GET for reads, POST for writes.
- Structured error responses: `{"error": "...", "detail": "..."}` with proper HTTP status codes.
- Input validation with Pydantic `BaseModel` subclasses.

## Adding a New Endpoint

1. Choose the appropriate router in `bannin/routes/`:
   - `llm.py` -- LLM-related endpoints
   - `intelligence.py` -- monitoring intelligence (alerts, predictions, chat)
   - `mcp.py` -- MCP sessions, Ollama
   - `analytics.py` -- event store queries
   - Or add to `api.py` if it's a core endpoint (metrics, status, processes)

2. Add the endpoint function with type hints and docstring.

3. Add a smoke test in `tests/test_api_endpoints.py`.

4. If the endpoint uses a POST body, create a Pydantic model for validation.

## Adding a New Chatbot Intent

1. Add a pattern to `_INTENT_PATTERNS` in `bannin/intelligence/chat.py` (order matters -- more specific patterns first).
2. Add a handler function `_handle_<intent>()`.
3. Register it in `_HANDLERS`.
4. Add parametrized test cases in `tests/test_chat_intents.py`.

## PR Process

1. Create a branch from `main`.
2. Make changes with tests.
3. Run `python -m pytest tests/ -v --tb=short` -- all must pass.
4. Commit with a clear message describing the change.
5. Open a PR with a summary and test plan.
