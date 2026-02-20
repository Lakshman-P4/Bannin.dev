# Bannin — Thought Diary & Origin Story

*This document started as the Phase 1b/1c planning doc when the project was still called "Vigilo." The original planning notes are preserved below. This opening section captures the personal side — how the project came to be, what I was thinking, and where I want it to go.*

---

## The Origin: Vigilo

The project started as **Vigilo** — Latin for "I watch." I chose that name because it captured exactly what I wanted to build: something that watches over your work when you can't. You hit run, you walk away, and something is keeping an eye on things for you.

Vigilo felt right at first. Clean, classical, meaningful. But as I researched more, I realised the name was too generic — too many things in the world are called Vigilo. Surveillance companies, security products, Latin mottos on police badges. I didn't want my product confused with any of that. I wanted something unique, something that when you Googled it, only my project came up.

## The Rebrand: Bannin (番人)

On 19 February 2026, I renamed the project to **Bannin** — 番人, Japanese for "watchman." Same meaning, completely different feel. Bannin sounds like a product. It's short, memorable, and the Japanese origin gives it a story. "What does Bannin mean?" is a better conversation starter than "It's Latin for I watch."

The rebrand was painful — 400+ references across 28+ files. Every import, every config, every test, every doc. But it was worth doing early before anyone else knew the old name. Better to change now than after launch.

I still like Vigilo. If the project grows, maybe I'll acquire that name someday. But for now, Bannin is the identity.

---

## What I'm Building and Why

The core idea is simple: **monitoring for the AI era.**

Everyone has monitoring for servers. Nobody has monitoring for the way regular people actually use computers now — running AI conversations, training models in cloud notebooks, using Claude Code to build things. Your ChatGPT conversation starts giving worse answers and you don't know why. Your Colab session dies at 3am and your training is lost. You walk away from a build and have no idea when it finishes.

"You hit run. You walk away. Then what?"

That's the hook. That's the entire product in one line.

## Who This Is Actually For

This was a big mental shift. I initially thought of Bannin as a developer tool — pip install, wrap your API calls, check a dashboard. And it is that. But it's also much more.

Anyone who uses AI is a potential user:
- **Students** running code on Colab who lose their work when sessions die
- **Writers** using Claude who don't know their conversation is degrading
- **Researchers** burning through GPU quotas on Kaggle without realising
- **Business professionals** using ChatGPT daily who don't understand why responses get worse
- **Developers** calling LLM APIs who want to track cost and context health
- **Anyone** who runs something and walks away

The browser extension path (tracking ChatGPT, Claude.ai, Gemini for everyday users) might matter more than the Python API wrapper. That's a huge audience that no existing tool serves.

---

## The Anxieties

### "Will anyone actually use this?"

This is the big one. I can build the most beautiful monitoring platform in the world and nobody might care. Most people don't even know their LLM conversations degrade. They don't know Colab sessions have time limits until they lose their work. The problem is real but invisible — people don't know they need a solution until it's too late.

The hope is that once someone experiences Bannin catching a problem before it happens — "Your session expires in 15 minutes, save now" or "This conversation is degrading, start fresh" — they'll never want to go without it.

### "Am I building something too big?"

Five components: Python agent, relay server, phone app, MCP server, browser extension. That's a lot for one person. Each component is a project on its own. The relay server alone needs authentication, WebSocket streaming, push notifications, and a database.

But the architecture is deliberate. Each piece is independent and useful on its own. The Python agent works locally without anything else. The MCP server works without the phone app. I don't need all five to launch — I need one or two done really well.

### "The competition might catch up"

Right now, nobody combines system monitoring + LLM tracking + cloud notebook awareness + phone alerts + MCP integration. But the big players (Datadog, Langfuse, W&B) have resources I don't. If this idea is good, someone bigger might build it.

The moat is speed and focus. They're building for enterprises with $500/month budgets. I'm building for the student on Colab, the writer on Claude, the solo developer calling APIs. Different audience, different price point ($5-7/month), different distribution (MCP organic adoption, not enterprise sales).

### "What if LLM conversations don't actually degrade the way I think?"

The entire conversation depreciation feature — which I believe is the strongest adoption driver — relies on the premise that long LLM conversations get worse. Context windows fill up, attention weakens, responses slow down. I've experienced this. Everyone I've talked to has experienced this. But I haven't proven it with data yet.

Phase 1c built the measurement tools. The health scoring function exists. The real proof will come when real users run Bannin across hundreds of conversations and we can see the degradation patterns in actual numbers.

### "What if none of this works out?"

This is the one that hits at 2am. What if I spend months building this and nobody downloads it? What if the market gap I see isn't actually a gap — it's just something people don't care about enough to pay for? What if I'm the only person who thinks LLM conversation monitoring is important?

I've sat with that fear. And then I look at the objective facts:

**The market gap is real.** I've researched every competitor. Helicone, Langfuse, Braintrust, LangSmith, W&B — they're all enterprise-focused, expensive, and none of them combine system monitoring + LLM tracking + cloud notebooks + phone alerts. The token counter Chrome extensions are single-platform, L0 only, no predictions, no actions. Nobody is building for the student on Colab or the writer on Claude. That gap isn't imagined. It's documented.

**The technology is incredible.** I'm building this with Claude Code — an AI that reads my entire codebase, writes production code, catches bugs, and helps me think through architecture. In any other era, building a five-component platform would require a team. Right now, one person with the right tools can move at the speed of a small startup. The tools I have access to are genuinely unprecedented. Claude Opus builds features in minutes that would take days by hand. The MCP ecosystem means distribution is built into the platform.

**The people around me push me forward.** The feedback I've gotten hasn't been polite nods — it's been "when can I use this?" and "have you thought about this use case?" People see the vision. The senior engineer analysis didn't say "nice idea" — it identified a real competitive moat and a real market opportunity. When smart people get excited about what you're building, that means something.

**The worst case isn't that bad.** Even if Bannin never becomes a business, I'll have built a real, working, multi-component monitoring platform from scratch. That's a portfolio piece that demonstrates architecture, product thinking, and execution. That has value regardless.

So yes, the anxiety is there. But the facts are louder than the fear.

---

## The Philosophy: Proactive, Not Passive

This is important enough to state clearly: **Bannin is not a dashboard you go and check. It's a system that comes to you when something matters.**

Most monitoring tools are passive. They show you numbers on a screen and wait for you to notice something wrong. That's fine for a DevOps engineer who stares at Grafana all day. It's useless for a student who started a training run and went to get coffee.

Bannin is proactive. It watches, it understands, and it **reaches out**:
- "Your conversation is getting slow. Start a new one?" — not a number on a screen, a recommendation on your phone
- "Your Colab session dies in 15 minutes. Save now." — not a timer you have to check, an alert that finds you
- "Your training is 80% done. ETA 12 minutes." — not a progress bar on a terminal you walked away from, a notification in your pocket

For non-technical users — someone who just uses ChatGPT every day — they should never need to understand what "context window" or "RAM percentage" means. Bannin translates all of that into **plain language actions**. "This chat is getting worse. Tap here to start fresh with everything important carried over." That's it. One tap.

This is the L2 (recommend) and L3 (act with consent) intelligence levels. The foundation exists. The alerts fire. Phase 3 gets them to your phone. Phase 4 makes them one-tap actionable. The vision is a system that keeps things optimal for any user — whether they have deep technical expertise or whether they just use LLMs excessively and want someone watching their back.

---

## Key Product Decisions (and why)

### Lead with health, not cost

Early on I made a choice: Bannin's headline is "your conversation is at 78% context, latency doubled, ~3 messages left" — not "$0.50 spent today." Cost tracking exists (it's free to calculate), but it's not the hook.

Why? Because "$0.50 spent" makes people shrug. "Your conversation is degrading" makes people act. Health drives behaviour. Cost is a spreadsheet.

### Conversation Depreciation & Context Transfer

This is the feature I believe will drive organic adoption more than anything else. Every power user of every LLM experiences the same frustration: long conversations get slow and dumb, but starting fresh means losing all your context.

Bannin detects the degradation AND solves the transition. "This chat is degrading. Start fresh? Here's everything important from the old one, compressed and ready to inject." Nobody else does this. Token counter extensions show a number. They don't detect degradation, don't recommend action, and don't solve the context loss.

### $5-7/month, not $50

I'm pricing low intentionally. This product was born from personally experiencing these problems. The goal is adoption first, not margin. Get users, get feedback, prove people will pay. Then adjust. Enterprise tiers ($100-300/month for teams) come later, naturally, when individual users bring Bannin to their workplaces.

### Open-source agent, closed relay + phone app

The Python agent is open-source. Anyone can install it, run it locally, extend it. The relay server and phone app are closed — that's where the business model lives. This means the free tier is genuinely useful (not crippled) and the paid tier adds convenience (phone alerts, history, cloud sync) rather than gating core features.

---

## The Potential

If this works — if people actually adopt Bannin — here's what I see:

**Short term**: A tool that Claude Code users love because it gives AI tools awareness of their own resource impact. MCP distribution is organic — every Claude Code session that connects to Bannin is a user acquired for free.

**Medium term**: The browser extension brings in the non-developer audience. Anyone using ChatGPT or Claude.ai gets conversation health monitoring and the "start fresh with context" feature. This could be millions of potential users.

**Long term**: Bannin becomes the default monitoring layer for the AI era. The way everyone has antivirus or a password manager, everyone who uses AI has Bannin watching their conversations, their compute, their spend. One dashboard, one phone app, everything you run.

**Far future — beyond monitoring**: This is the part I think about most. Monitoring is where Bannin starts, but it's not where it ends. As the user base grows and we understand how people actually interact with AI, Bannin should evolve from watching to **helping**.

Imagine: you're a first-time ChatGPT user and you're getting bad answers. Today, you don't know why. Maybe your prompts are vague. Maybe you're asking the wrong model. Maybe your conversation is too long. Bannin already knows all of this — it tracks context health, latency, model choice. The next step is using that knowledge to actively help you get better results.

- "Your prompts are averaging 8 words. Try being more specific — here's a suggestion."
- "You've been using GPT-3.5 for complex analysis. GPT-4o would give significantly better results for this type of question."
- "You're asking follow-up questions that repeat context. Try referencing your earlier message instead — it's faster and cheaper."
- "This conversation has covered 6 different topics. Consider splitting it into focused chats for better answers."

That's prompt engineering assistance — not as a course you take or a guide you read, but as real-time, contextual nudges from a system that's already watching your conversations. Bannin wouldn't just tell you things are going wrong. It would help you make things go right.

And it goes further. Bannin could become the environment where people learn to use AI effectively. Not through tutorials, but through doing. You use AI the way you normally do. Bannin watches, learns your patterns, and gently guides you toward better habits. Over time, you become a more effective AI user without ever sitting through a lesson.

The vision is bigger than monitoring. It's a **proactive, AI-friendly digital environment** — a companion layer that sits between people and the AI tools they use, making everything work better. For builders, it optimises their workflows, catches problems before they happen, and keeps their systems healthy. For everyday users, it demystifies AI, helps them get more value from the tools they're already paying for, and grows with them as they grow.

Monitoring is the foundation. Intelligence is the engine. But the destination is making every person who uses AI — whether they're a student, a writer, a developer, or someone who just discovered ChatGPT last week — more capable, more confident, and more in control of their digital environment.

That's what Bannin is for. That's where this goes.

That's the dream. The reality is I'm one person with a laptop, $400/year budget, and a lot of conviction. But every big thing started small.

---

## The Journey So Far

### Phase 1a (18 Feb 2026) — The Engine
Built the Python agent. pip install, localhost API, system metrics. Proved the core concept works. Hit Windows PATH issues and port conflicts, but nothing blocking.

### Phase 1b (18 Feb 2026) — Platform Awareness
Taught Bannin to recognise Colab and Kaggle. Tested on real platforms. Discovered our disk estimates were wrong. Built the remote config system.

### Phase 1c (18 Feb 2026) — LLM Eyes
Built the LLM wrapper. 30+ models, 7 providers, context prediction, latency detection. Made the product decision to lead with health over cost.

### Phase 2 (19 Feb 2026) — The Brain
Added intelligence: OOM prediction, progress tracking, threshold alerts, metric history. Built the live dashboard. Verified MCP integration with Claude Code.

### Rebrand (19 Feb 2026) — Vigilo becomes Bannin
400+ references changed across 28+ files. Clean break, new identity.

### Post-Phase 2 Fixes (19 Feb 2026) — Polish
Fixed dashboard bugs (process display, OOM UX), MCP intelligence auto-start, collection speed (5s to 2s), offline flicker. The dashboard went from "prototype with bugs" to "something I'd show someone."

---

### Dashboard UX Overhaul (20 Feb 2026) — Making It Real

The dashboard went from "developer prototype" to "something I'd actually show a friend." Loading eye animation with the Bannin logo (eye slit opening to reveal the orb), friendly process names, plain-English summaries, smart alerts that disappear when the problem goes away. Fixed a critical bug where Bannin itself was using 99.6% CPU — the monitoring tool was the heaviest process on the machine. Humbling.

Also updated the MCP server so Claude Code sees friendly names. Small thing, but it means the AI tools that connect to Bannin get the same quality experience as humans using the dashboard.

---

## Reflections — 20 February 2026

### Feeling: Confident. Motivated. Grounded.

Today something shifted. Not the code — the code has been working for days. What shifted is conviction.

I talked to Prashanth sir — CTO at ThinkingCode. Not someone who gives polite encouragement. Someone who's built things, shipped things, and knows what it takes to turn code into a product.

His advice was clear and practical:

**"Keep it open source. Get feedback. But when you find yourself in the moat zone — when the thing you've built is genuinely defensible — THAT is when you go private. That's when you release it as a downloadable package on any laptop, as an MCP server, as a Chrome extension, as a phone app. But get it to that point first."**

This reframes my thinking. I was anxious about the open-source vs. closed-source decision. His framing makes it simple: open source is the learning phase. You ship it, people use it, they tell you what's wrong, what's missing, what they'd pay for. You iterate in public. The feedback loop is the product development.

Then when the architecture is proven, the moat is real (unified relay, conversation depreciation, intelligence levels, MCP distribution), and you've validated that people actually want this — that's when you flip the switch. Not before.

### What the moat looks like today

Honestly? It's forming but it's not there yet.

What I have:
- A working monitoring agent (system + LLM + cloud notebooks) — nobody else has this combination
- MCP integration — organic distribution through Claude Code, Cursor, Windsurf
- Intelligence engine (OOM prediction, alerts, progress tracking) — not just L0 observe, actual L1 alerts
- Conversation health scoring (built, not yet exposed) — the foundation of the "wow" feature
- A dashboard that speaks human, not metrics

What I don't have yet:
- Real users (the product hasn't been shared publicly)
- Proven conversation depreciation (the health scoring exists but hasn't been battle-tested)
- The browser extension (the biggest audience unlock)
- Phone alerts (the "comes to you" promise)
- Any revenue or willingness-to-pay signal

The moat is technical today. It needs to become experiential — people need to feel the difference Bannin makes. "I didn't lose my Colab session because Bannin warned me." "I started a fresh chat because Bannin told me this one was degrading, and the new conversation was immediately better." Those moments are the moat. The code is just the scaffolding.

### The plan, adjusted

Prashanth sir's advice aligns with the reordered phase plan. Ship open source first (Phase 3 — PyPI launch). Get it into people's hands. Build the browser extension (Phase 4 — biggest audience). Let real usage data tell me where the moat actually is. Then when there's a clear defensible position, go private and build the paid product.

The anxiety from a few days ago — "will anyone use this?" — is still there. But it's quieter now. The product works. The dashboard is genuinely pleasant to use. The summary speaks in plain English. The alerts are accurate. This isn't a prototype anymore. It's a product that needs users.

### On building with AI

Something I keep reflecting on: I'm building a monitoring platform for AI tools, using an AI tool. Claude Code is writing production code, catching bugs, suggesting architecture, thinking through product decisions. In any other era, this would require a team of 3-5 engineers working for months. Instead it's one person with a laptop and an AI partner, building at startup speed.

This isn't just a tool advantage. It's a signal about the future Bannin is building for. If one person can build this fast, imagine what happens when everyone is building this fast. The number of AI-dependent workflows is about to explode. Every one of those workflows needs monitoring. Every one of those users is a potential Bannin user.

The market isn't just people who use AI today. It's everyone who will use AI tomorrow. And that's everyone.

---

*What's next: Phase 3 — LLM Health Exposure + PyPI Launch. Ship it. Get feedback. Find the moat.*

*Last updated: 20 February 2026*

---
---

# Original Planning Notes (from when the project was "Vigilo")

*The notes below are preserved from the original planning phase. All of this has since been built and tested — see `development_log.md` for the actual build results. References to "Vigilo" are historical.*

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
