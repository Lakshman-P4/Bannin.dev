# Bannin

**番人** (Japanese for "watchman") — a universal monitoring agent for your machine, your LLMs, and your cloud notebooks.

*I watch so you don't have to.*

---

## What It Does

Bannin runs on your machine (or inside a cloud notebook) and monitors everything: CPU, RAM, GPU, disk, running processes, LLM API usage, and cloud session health. It predicts out-of-memory crashes before they happen, fires smart alerts, and gives you a plain-English summary of how your system is doing.

It also works as an **MCP server** — meaning AI coding tools (Claude Code, Cursor, Windsurf) can query your system health through natural conversation.

## Install

```bash
pip install -e .
```

To include GPU monitoring and MCP server support:

```bash
pip install -e ".[all]"
```

## Quick Start

**Start the agent:**

```bash
python -m bannin.cli start
```

**Open the dashboard:**

Visit [localhost:8420](http://localhost:8420) in your browser.

**Use with Claude Code (MCP):**

The included `.mcp.json` configures Bannin as an MCP server automatically. Ask Claude things like:
- "How's my system doing?"
- "What processes are using the most memory?"
- "Am I going to run out of RAM?"

## What You Get

**System Monitoring**
- CPU, RAM, disk, network — real-time with history
- GPU monitoring (NVIDIA via pynvml)
- Top processes by resource usage with friendly names
- Plain-English system health summaries

**Intelligence**
- OOM (out-of-memory) prediction with confidence scores
- Smart alerts with cooldowns (17+ configurable rules)
- Training progress detection (tqdm interception, stdout parsing)
- ETA estimation for long-running tasks

**LLM Tracking**
- Wrap OpenAI, Anthropic, and Google API clients to track token usage and cost
- Context window exhaustion prediction
- Latency degradation detection
- Cost calculation across 30+ models and 7 providers

**Cloud Notebooks**
- Google Colab: session time, GPU type changes, VRAM, storage, tier detection
- Kaggle: GPU quota tracking, session limits, output size, internet detection

**MCP Server**
- `get_system_metrics` — full system snapshot
- `get_running_processes` — top processes by CPU/memory
- `predict_oom` — memory exhaustion prediction
- `get_training_status` — tracked task progress
- `get_active_alerts` — current monitoring alerts

**Live Dashboard**
- Real-time metrics at [localhost:8420](http://localhost:8420)
- Memory usage chart with 30-minute history
- Process list, alerts, OOM status, LLM usage
- Loading animation, auto-refresh

## Trial Guides

Pick the guide that matches your setup:

| Guide | For |
|---|---|
| [trial.md](trial.md) | Claude Code users |
| [trial-vscode.md](trial-vscode.md) | VS Code, Cursor, Windsurf (MCP via editors) |
| [trial-colab.md](trial-colab.md) | Google Colab and Kaggle notebooks |
| [trial-powershell.md](trial-powershell.md) | Terminal / command line (any OS) |

## API

The agent exposes a local REST API at `localhost:8420`:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Agent alive check |
| `GET /metrics` | Full system snapshot (CPU, RAM, disk, network, GPU) |
| `GET /status` | Agent identity (hostname, OS, version, uptime) |
| `GET /processes` | Top processes by resource usage |
| `GET /summary` | Plain-English system health summary |
| `GET /llm/usage` | LLM session health and usage summary |
| `GET /llm/calls` | Recent LLM API call history |
| `GET /llm/context` | Context window exhaustion prediction |
| `GET /llm/latency` | Response latency trend analysis |

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

## What's Coming

- Conversation health scoring and "start new chat" recommendations
- Phone alerts (push notifications when tasks finish or systems need attention)
- Browser extension for ChatGPT, Claude.ai, and Gemini monitoring
- macOS Apple Silicon GPU support
- PyPI publication (`pip install bannin`)

## Status

This is an early build. Core monitoring, intelligence, and MCP integration are working. Looking for honest feedback.

## License

[MIT](LICENSE)
