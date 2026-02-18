# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vigilo is a universal monitoring platform that watches everything you run — your machine, your LLMs, your cloud notebooks, your coding tools — and puts it all on your phone. It's not just a system resource monitor. It's a health dashboard for your entire digital workflow.

**Who it's for**: everyone in the digital era. Not just developers — anyone who uses AI. If you use ChatGPT and your conversation starts giving worse answers, Vigilo tells you why and helps you fix it. If you're a student running code on Colab, Vigilo warns you before your session dies. If you're a writer using Claude and want to know when to start a fresh chat, Vigilo watches for you. If you're a developer calling LLM APIs, Vigilo tracks your usage. If you're running a build and walk away, Vigilo pings your phone when it's done. The audience is anyone who interacts with AI or compute — students, writers, researchers, creators, business professionals, hobbyists, and yes, developers too.

**Core hook**: "You hit run. You walk away. Then what?"

## Current State

- **Phase 1a: Python Agent Core** — COMPLETE (18 February 2026)
- **Phase 1b: Cloud Notebook Monitoring (Colab/Kaggle)** — COMPLETE (verified on real Colab + Kaggle, 18 February 2026)
- **Phase 1c: LLM Health Monitoring & Token Tracking** — COMPLETE (18 February 2026)

The Python agent is functional: `pip install vigilo`, `vigilo start`, and the local API at `localhost:8420` serves live system metrics. See `development_log.md` for full details of what was built, tested, and the challenges encountered.

## Architecture

Five core components, connected via WebSocket to a unified relay:

1. **Python Agent** (`vigilo/`) — installed via `pip install vigilo`, runs on the user's machine or inside cloud notebook kernels (Colab, Kaggle). Collects system metrics (CPU, RAM, GPU, disk) using `psutil`, `pynvml`, and ML-specific hooks (`torch.cuda`, `tqdm` interception). Exposes a local REST API at `localhost:8420`.

2. **Relay Server** (Node.js) — aggregates data from all agent types (Python agents, browser extensions), handles email-based authentication (Firebase Auth), stores run history, and dispatches push notifications (FCM/APNs) to the phone app.

3. **Phone App** (React Native) — unified dashboard: live metrics, alerts, action buttons (Pause/Checkpoint/Kill), LLM cost dashboard, and history across all monitored environments.

4. **MCP Server** (`vigilo-mcp`) — exposes Vigilo as a Model Context Protocol server so AI tools (Claude Code, Cursor, Windsurf) can query system status via standardized tool calls. Built on Anthropic's MCP Python SDK, JSON-RPC 2.0, stdio transport.

5. **Browser Extension** (Chrome/Manifest V3) — monitors LLM web UIs (ChatGPT, Claude.ai, Gemini) and cloud coding tools (Codex, Replit) for token estimation, response latency degradation, conversation health scoring, and task completion. Sends data to the relay like any other agent.

```
User's Machine                              Cloud                    Mobile
┌──────────────────────────────────┐
│ Python Agent  <-->  MCP Server   │─WebSocket──▶ Relay Server ◀─Push─▶ Phone App
│ (localhost:8420)                 │             (Node.js)              (React Native)
└──────────────────────────────────┘                 ▲
                                                     │
Browser Extension ───────────────────────────────────┘
(ChatGPT/Claude.ai/Gemini/Codex)
```

## Agent API Endpoints (localhost:8420)

| Endpoint | Method | Purpose | Status |
|---|---|---|---|
| `/health` | GET | Agent alive check | ✅ Built |
| `/metrics` | GET | Full system snapshot (CPU, RAM, disk, network, GPU) | ✅ Built |
| `/status` | GET | Agent identity (hostname, OS, version, uptime) | ✅ Built |
| `/processes` | GET | Top processes by resource usage | ✅ Built |
| `/tasks` | GET | Monitored jobs (training runs, notebooks) | ✅ Placeholder |
| `/predict` | GET | OOM prediction, ETA | 🔜 Phase 2 |
| `/actions` | POST | Trigger checkpoint, pause, kill | 🔜 Phase 4 |
| `/ws` | WebSocket | Live metric stream to relay | 🔜 Phase 3 |
| `/llm/usage` | GET | LLM session health & usage summary | ✅ Built |
| `/llm/calls` | GET | Recent LLM API call history | ✅ Built |
| `/llm/context` | GET | Context window exhaustion prediction | ✅ Built |
| `/llm/latency` | GET | Response latency trend analysis | ✅ Built |

## Target Platforms & Use Cases

| Platform | Agent Type | Who Uses It | Monitors | Key Alerts |
|---|---|---|---|---|
| Any local machine | Python package | Anyone coding | CPU, RAM, GPU, disk, processes | High usage, process done, system strain |
| Google Colab | Python in notebook | Students, ML engineers | Session time, GPU type/realloc, VRAM, storage | Session expiry, GPU reassigned, auto-checkpoint |
| Kaggle Notebooks | Python in notebook | Data scientists, students | Weekly GPU quota, session limits, storage | Quota running low, session timeout, save reminder |
| LLM APIs (dev) | Python middleware | Developers using OpenAI/Anthropic/etc. | Tokens, cost, latency, context window | Spend alerts, context exhaustion, latency spikes |
| LLM web UIs | Browser extension | Anyone using ChatGPT/Claude/Gemini | Est. tokens, response time, conversation health | Chat degrading, "start new chat", slow responses |
| AI coding tools | Python agent + MCP + browser ext | Developers using Claude Code/Codex/Cursor | Spawned processes, system load, cost | Build done, test done, token spend, throttling |

### Google Colab Monitoring

The Python agent runs inside the notebook kernel (`!pip install vigilo`). Monitors Colab-specific concerns:
- **Session time remaining** — Colab free tier disconnects after ~90min idle / ~12hr max. Vigilo tracks elapsed time and warns before timeout.
- **GPU type and reallocation** — Colab may switch your GPU (T4 → P100 → none) mid-session. Vigilo detects GPU type changes and alerts if your GPU gets reassigned.
- **VRAM limits** — fixed per GPU type (T4=16GB, P100=16GB, A100=40GB). Vigilo tracks VRAM usage and predicts OOM within these hard limits.
- **Ephemeral storage** — Colab's disk is temporary. Vigilo monitors disk usage and triggers auto-checkpoint to Google Drive before session death.
- **Runtime restarts** — detects when Colab restarts the runtime (kernel crash, manual restart) so you know your state was lost.

### Kaggle Notebook Monitoring

Kaggle has its own set of resource constraints distinct from Colab:
- **Weekly GPU quota** — Kaggle gives ~30 hours/week of GPU time (P100). Vigilo tracks cumulative usage and warns when quota is running low ("You have 4.2 hours of GPU left this week").
- **Session time limits** — Kaggle sessions max out at ~12 hours (CPU) or ~9 hours (GPU). Vigilo counts down and alerts before timeout.
- **Internet access restrictions** — some competitions disable internet. Vigilo detects this and warns if your code tries to download data.
- **Output storage limits** — Kaggle limits output to ~20GB. Vigilo monitors output size and warns before you hit the cap.
- **Accelerator availability** — TPU and GPU availability fluctuates. Vigilo detects your assigned accelerator type and alerts on changes.

### LLM Monitoring

This is a core differentiator — Vigilo treats LLMs as systems that need monitoring, just like servers.

**For API users** (developers calling OpenAI, Anthropic, Google APIs):
- Python middleware wraps API calls and intercepts responses containing exact token counts
- Two integration patterns: `with vigilo.track(): client.chat.completions.create(...)` or `client = vigilo.wrap(OpenAI())`
- Tracks cumulative tokens per conversation/session, cost in dollars, and latency trends
- Predicts context window exhaustion ("You've used 87K of 128K tokens — ~3 messages left")
- Spend alerts ("You've spent $4.20 today across 12 conversations")
- Latency degradation detection (response times climbing = overloaded model endpoint)
- Maintained model pricing table for cost calculation across providers

**For web UI users** (anyone using ChatGPT, Claude.ai, Gemini in browser):
- Browser extension parses DOM to estimate token count (~4 chars/token heuristic for English)
- Timestamps each response to detect latency degradation (response took 8s → 15s → 23s = degrading)
- Conversation health score — long conversations get slower and dumber, Vigilo detects this
- "Start new chat" recommendation with optional auto-summary to carry context forward
- Session tracking — how long you've been chatting, estimated cost (for paid tiers)

**For everyone**:
- Daily/weekly LLM usage summaries sent to phone
- Cross-platform view: see all your LLM usage (API + web) in one dashboard
- Cost tracking across providers (OpenAI + Anthropic + Google in one view)

### Conversation Depreciation & Context Transfer

This is a priority feature and potentially the strongest adoption driver for the entire platform.

**The problem**: As LLM conversations get longer, they degrade. Context windows fill up, attention over long sequences weakens, and the model starts "forgetting" earlier parts of the conversation. Users face a trap: stale long chat = slow and dumb, fresh new chat = fast but amnesia. Platform memory systems (like Claude Projects) capture broad themes across conversations but not the specific working state of a single conversation.

**The solution — two implementation paths:**

**Path 1: API Middleware (Phase 1c)** — For developers using LLM APIs. The middleware detects context window exhaustion and can automatically generate a compressed context summary (key decisions, in-progress work, established facts) for injection into the next API conversation. Ships early because it builds on the same token tracking infrastructure.

**Path 2: Browser Extension (Phase 6)** — For web UI users. The extension tracks conversation health (latency trending, token estimation, health score). When health drops below threshold, it surfaces a recommendation: "This conversation is degrading. Start fresh?" If accepted, it captures the conversation's key context via DOM, generates a structured summary, and injects it into the new chat. The user gets a fast, fresh conversation that knows everything important from the old one.

**Why this matters**: No existing tool solves the conversation transition problem. Token counter extensions only show a number. They don't detect degradation, don't recommend action, and don't solve the context loss when starting fresh. This feature alone could drive organic adoption because every power user of every LLM experiences this frustration daily.

### AI Coding Tools (Claude Code / Codex / Cursor)

Three integration layers:
1. **Python agent** on the local machine monitors processes spawned by Claude Code (builds, tests, installs, git ops) and reports system impact
2. **MCP server** lets Claude Code query its own resource footprint — check system load before spawning heavy tasks, see what other sessions started, send phone alerts when done
3. **Browser extension** tracks Codex cloud tasks — completion notifications, cost estimation, failure alerts

Key MCP tools: `get_system_metrics`, `get_running_processes`, `get_training_status`, `predict_oom`, `checkpoint_model`, `adjust_batch_size`, `notify_user`, `get_session_cost`.

## Agent Intelligence Levels

The agent progressively evolves through these capability tiers. This is the core moat — most monitoring tools stop at L0.

- **L0 Observe** — report raw metrics ("CPU at 85%", "3.2K tokens used") — **COMPLETE**
- **L1 Alert** — threshold-based warnings ("OOM in ~12min", "Colab session expires in 20min", "Context window 90% full")
- **L2 Recommend** — rule-based suggestions ("checkpoint now", "reduce batch size", "start new chat — this one is degrading")
- **L3 Act (with consent)** — actionable buttons on phone ("Pause Training", "Save Checkpoint", "Open New Chat with Summary")
- **L4 Act (autonomous)** — policy-driven auto-actions ("Auto-checkpointed before Colab timeout")

## Competitive Context

No existing tool combines system monitoring + LLM cost tracking + cloud notebook awareness + phone alerts + MCP integration + actionable intelligence (L0–L4). The landscape is fragmented:

- **LLM observability tools** (Helicone, Langfuse, Braintrust, LangSmith, Datadog) — enterprise-focused, expensive, no phone alerts, no system metrics, no personal/student use case
- **ML training monitors** (W&B, Neptune) — no system monitoring, no phone alerts, no LLM cost tracking
- **Mobile training monitors** (TF Watcher, HyperDash) — both abandoned/deprecated, validating demand with no supply
- **System MCP monitors** (mcp-monitor, Netdata) — L0 only, no prediction, no actions, no LLM awareness
- **Token counter extensions** (ChatGPT Token Monitor, ChatGPT Token Counter) — single-platform, L0 only, no latency/health, no phone, no recommendations

Vigilo's moat: unified relay (one dashboard for everything), intelligence levels (L0→L4), MCP distribution (organic adoption via Claude Code), and LLM-as-infrastructure monitoring (genuinely new category).

## Build Phases

### Phase 1a: Python Agent Core — ✅ COMPLETE
- Python package structure (pip install vigilo)
- psutil metrics collector (CPU, RAM, disk, network)
- GPU monitoring module (pynvml)
- Process monitor (top processes by usage)
- FastAPI local API on localhost:8420
- CLI entry point (vigilo start / status / stop)
- vigilo.watch() context manager

### Phase 1b: Cloud Notebook Monitoring — ✅ COMPLETE
- Environment detection: is_colab(), is_kaggle(), is_local() — verified on real platforms
- Colab: session time, tier detection, GPU tracking, RAM, storage, Drive, compute units, hard limits
- Kaggle: session time, GPU/TPU quotas, dual-GPU detection, output tracking, internet detection, hard limits
- /platform API endpoint with comprehensive monitoring data
- Warning system at multiple severity levels
- Real-world tested: Colab free tier + Kaggle CPU (competition mode)

### Phase 1c: LLM Health Monitoring & Token Tracking — ✅ COMPLETE
- vigilo.wrap() for OpenAI, Anthropic, Google clients (+ auto-detection of OpenAI-compatible providers)
- vigilo.track() context manager for named tracking scopes
- Token counting per call (input, output, cached tokens)
- Cost calculation per call (30+ models across 7 providers, remotely updateable pricing)
- Context window exhaustion prediction ("74.2% used, ~1 message remaining")
- Latency degradation detection ("Latency increasing: 1.4s → 4.0s")
- 4 new API endpoints: /llm/usage, /llm/calls, /llm/context, /llm/latency
- Smart model name matching (handles date-suffixed variants)
- Double-wrap protection, mock-tested with simulated clients

### Phase 2: Intelligence Engine
- OOM prediction engine (memory growth rate extrapolation, >70% confidence threshold)
- Progress detection (tqdm hook, stdout regex parsing)
- ETA calculator
- Threshold engine for L1 alerts
- MCP server (basic — get_system_metrics, get_training_status, predict_oom)

### Phase 3: Connectivity
- Node.js relay server (DigitalOcean, $10-15/mo)
- Email authentication (Firebase Auth magic link)
- WebSocket streaming (agent → relay, 10-second intervals)
- Push notifications (FCM/APNs)
- Run history storage (SQLite)

### Phase 4: MCP Server + AI Integration
- Full MCP tool suite (metrics, tasks, training, OOM, actions)
- Claude Code / Cursor / Windsurf testing
- Action tools (checkpoint, pause, kill — L3 with user confirmation)
- Integration docs ("Connect Vigilo to Claude Code in 2 minutes")
- Rule-based recommendation engine (L2)

### Phase 5: Phone App + Actions
- React Native scaffold (Expo)
- Alert screen, live status, action buttons (L3)
- Run history screen
- LLM cost dashboard (cross-provider)
- TestFlight / internal Android beta

### Phase 6: Polish + Launch + Browser Extension
- Browser extension (ChatGPT/Claude.ai/Gemini — conversation health, context transfer)
- macOS Apple Silicon (macmon integration)
- OpenClaw skill publication
- Policy-based auto-actions (L4)
- LLM-powered recommendations
- Documentation site, PyPI release, App Store submission
- Community launch (Reddit, HN, Kaggle)

## Key Design Decisions

- **API-first**: all components communicate through REST/WebSocket interfaces so any frontend can be built on top
- **Email auth**: simple email-based identity links all agents → relay → phone app (Firebase Auth)
- **pip-installable agent**: `pip install vigilo` with decorator/context manager API
- **Cross-platform agents**: Python agent for ML/local, browser extension for web UIs
- **MCP integration**: Vigilo as MCP server creates feedback loop — AI tools query their own health
- **Unified relay**: all agent types feed into same relay and phone app — one dashboard for everything
- **Broad audience**: everyone who uses AI or compute — not a developer tool, a digital-era tool
- **Bootstrapped**: total cost under $400/year, no VC dependency

## Key Python Packages

- `psutil` — CPU, RAM, disk, network (all platforms)
- `pynvml` — NVIDIA GPU monitoring (Windows/Linux)
- `macmon` — Apple Silicon GPU, ANE, thermals (macOS, via subprocess)
- `fastapi` + `uvicorn` — local API server
- `websockets` — relay connection
- `mcp` (Anthropic SDK) — MCP server
- `tqdm` — progress bar interception
- `torch` (optional) — PyTorch-specific hooks
- `click` — CLI framework

## Cross-Platform Matrix

| Feature | macOS (Apple Si) | Windows/Linux |
|---|---|---|
| CPU/RAM/Disk | psutil | psutil |
| GPU monitoring | macmon | pynvml (NVIDIA) |
| Thermal data | powermetrics | NVIDIA thermal |
| Neural Engine | macmon (ANE) | N/A |
| PyTorch CUDA | N/A (MPS instead) | torch.cuda |
| Process management | psutil + signal | psutil + signal |
| Daemon mode | launchd | systemd / Windows Service |

## Security Model

- **Agent ↔ Relay**: WebSocket over TLS (wss://), authenticated with email token, agent never exposes ports to internet
- **Relay ↔ Phone**: HTTPS REST + Firebase Auth, JWT per session
- **MCP Server**: localhost only (stdio transport), no network exposure, inherits host app security
- **Browser Extension**: no data collection, DOM parsing runs locally, sends only metrics to relay via authenticated connection
- **Agent Actions**: L3 requires explicit user confirmation, L4 requires user-defined policy, no action without consent by default

## Known Issues / Constraints from Phase 1a

- **Windows PATH**: CLI may not be on PATH after pip install --user. Workaround: `python -m vigilo.cli start`. Document in README.
- **Port conflict**: Starting agent twice causes port 8420 conflict. Need graceful detection ("Vigilo already running").
- **GPU untested**: pynvml code written but not tested on NVIDIA hardware. Needs testing on GPU machine or Colab.
- **Colab/Kaggle verified**: Tested on real platforms. Colab disk was 107 GB (not 50 GB assumed). Kaggle uses 8 TB shared filesystem (focus on 20 GB output limit). Both corrected.

## References

- `Vigilo.docx` — Original system architecture (3-component version)
- `Vigilo_Senior_Engineer_Notes_Analysis.md.pdf` — Senior engineer feedback + strategic analysis
- `Vigilo_Master_Architecture_v2.docx` — Unified master doc (5-component, competitive analysis, full roadmap)
- `development_log.md` — Running build log with test results and challenges
