# Bannin

**番人** (Japanese for "watchman") — a universal monitoring agent for your machine, your LLMs, and your cloud notebooks.

*You hit run. You walk away. Then what?*

---

## What It Does

Bannin runs on your machine (or inside a cloud notebook) and monitors everything: CPU, RAM, GPU, disk, running processes, LLM conversation health, API usage, and cloud session health. It predicts out-of-memory crashes before they happen, scores your AI conversation quality, fires smart alerts, and gives you plain-English summaries of how your system is doing.

It also works as an **MCP server** — meaning AI coding tools (Claude Code, Cursor, Windsurf) can query your system health through natural conversation.

## Install

```bash
pip install bannin
```

With GPU monitoring and MCP server support:

```bash
pip install "bannin[all]"
```

## Quick Start

**Start the agent:**

```bash
bannin start
```

**Open the dashboard:**

Visit [localhost:8420](http://localhost:8420) in your browser.

**Use with Claude Code (MCP):**

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "bannin": {
      "command": "python",
      "args": ["-m", "bannin.mcp"]
    }
  }
}
```

Then ask Claude things like:
- "How's my system doing?"
- "What processes are using the most memory?"
- "Am I going to run out of RAM?"
- "How healthy is this conversation?"

## Features

### System Monitoring
- CPU, RAM, disk, network -- real-time with 30-minute history
- GPU monitoring (NVIDIA via pynvml)
- Top processes by resource usage with friendly names and category badges
- Process descriptions and tooltips for 97 common applications
- Plain-English system health summaries

### Intelligence
- OOM (out-of-memory) prediction with confidence scores and time-to-crash estimates
- Smart alerts with cooldowns (17+ configurable rules)
- Training progress detection (tqdm interception, stdout parsing)
- ETA estimation for long-running tasks
- L2 recommendations -- actionable suggestions from cross-signal analysis (12 rules)
- Built-in chatbot for natural language system health queries

### LLM Health Monitoring
- Conversation health scoring (7 signals, 0-100 score) across Claude Code, Cursor, Windsurf, Ollama
- Real Claude Code session data via JSONL transcript reading (actual token counts)
- MCP session tracking with fatigue scoring and token estimation
- Ollama local LLM monitoring -- auto-detect, VRAM tracking, model load/unload
- LLM connection scanner -- detects 9 AI tool types running on your system
- Per-source health breakdown with combined worst-of scoring

### LLM API Tracking
- Wrap OpenAI, Anthropic, and Google API clients to track token usage and cost
- Context window exhaustion prediction
- Latency degradation detection
- Cost calculation across 30+ models and 7 providers

### Cloud Notebooks
- Google Colab: session time, GPU type changes, VRAM, storage, tier detection
- Kaggle: GPU quota tracking, session limits, output size, internet detection

### Persistent Analytics
- Event pipeline with SQLite + FTS5 full-text search
- Query history by type, severity, or keyword
- 30-day retention with automatic pruning
- Separate analytics dashboard at port 8421

### MCP Server (9 Tools)
- `get_system_metrics` -- full system snapshot (CPU, RAM, disk, network, GPU)
- `get_running_processes` -- top processes by CPU/memory with friendly names
- `predict_oom` -- memory exhaustion prediction with confidence
- `get_training_status` -- tracked task progress and ETAs
- `get_active_alerts` -- current monitoring alerts
- `check_context_health` -- conversation health score with component breakdown
- `get_recommendations` -- L2 actionable recommendations
- `query_history` -- search analytics event history
- `search_events` -- full-text search across stored events

### Live Dashboard
- Real-time metrics with color-coded gauges (cyan/amber/red)
- Visual urgency indicators (amber glow at 60%, red pulse at 80%+)
- Conversation health accordion with per-source breakdown
- Connection badges for auto-detected LLM tools
- Memory trend chart (5-minute rolling)
- Process table with friendly names and hover tooltips
- OOM prediction display
- Alert banner with severity indicators
- Built-in chatbot ("Ask Bannin") with 15 intents
- Loading eye animation

## API

The agent exposes a local REST API at `localhost:8420`:

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Agent alive check |
| `/status` | GET | Agent identity (hostname, OS, version, uptime) |
| `/metrics` | GET | Full system snapshot (CPU, RAM, disk, network, GPU) |
| `/processes` | GET | Top processes with friendly names and categories |
| `/summary` | GET | Plain-English system health summary |
| `/chat` | POST | Chatbot (natural language system health assistant) |
| `/alerts` | GET | Full alert history for this session |
| `/alerts/active` | GET | Currently active alerts |
| `/predictions/oom` | GET | OOM prediction with confidence |
| `/history/memory` | GET | Memory usage history over last N minutes |
| `/tasks` | GET | Tracked tasks (training progress, ETAs) |
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
| `/analytics/timeline` | GET | Event timeline |
| `/platform` | GET | Cloud notebook platform info (Colab/Kaggle) |
| `/stream` | GET | Server-Sent Events for live dashboard updates |

## Python API

```python
import bannin

# Monitor system during a block of code
with bannin.watch():
    train_model()

# Wrap an LLM client to track tokens and cost
import openai
client = bannin.wrap(openai.OpenAI())

# Track a specific scope
with bannin.track("my-experiment"):
    response = client.chat.completions.create(...)
```

## CLI

```bash
bannin start                    # Start the agent (dashboard at localhost:8420)
bannin start --port 9000        # Start on a custom port
bannin mcp                      # Start the MCP server (stdio transport)
bannin analytics                # Start the analytics dashboard (port 8421)
bannin history                  # Query stored event history
bannin history --since 2h       # Events from the last 2 hours
bannin history --search "OOM"   # Full-text search
bannin history --json           # Raw JSON output
```

## What's Coming

- Phone alerts (push notifications when tasks finish or systems need attention)
- Browser extension for ChatGPT, Claude.ai, and Gemini monitoring
- Context transfer -- carry conversation state to a fresh chat when health degrades
- macOS Apple Silicon GPU support
- Shareable dashboards via bannin.dev

## Requirements

- Python 3.9+
- Works on Windows, macOS, and Linux

## License

[MIT](LICENSE)
