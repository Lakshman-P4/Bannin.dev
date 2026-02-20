# Bannin - Priority & Ideas

What we're working on, what's next, and ideas for the future. Updated as things move.

---

## Current Priority: Phase 3 - LLM Health Exposure + PyPI Launch

The health scoring engine already exists (`bannin/llm/health.py`) but isn't exposed anywhere yet. This is the "wow" feature -- the thing that makes someone go "oh, this is actually useful" instead of just seeing numbers. We don't publish to PyPI until this works.

### What needs to happen
- [ ] Expose health score as an API endpoint (`/llm/health`)
- [ ] Wire health scoring into the LLM tracker (auto-calculate during API calls)
- [ ] Add health score to the dashboard (visual health gauge)
- [ ] Add health score to MCP server tools
- [ ] L2 recommendation engine ("start new chat", "reduce batch size", "checkpoint now")
- [ ] macOS compatibility testing (psutil, dashboard, MCP on Apple Silicon)
- [ ] Cursor / Windsurf MCP testing
- [ ] PyPI publication (`pip install bannin`)
- [ ] Documentation site + quick-start guide
- [ ] Community launch (Reddit, HN, Kaggle)

---

## How LLM Health Tracking Works (Non-Technical Explanation)

Think of an AI conversation like a phone call on a walkie-talkie with limited battery. When the call starts, everything is clear -- fast responses, good answers. But as the conversation goes on, three things happen:

**1. The conversation fills up (Context Freshness)**

Every AI has a memory limit for each conversation. Early on, you've barely used any of it -- like a notebook with mostly blank pages. As you keep chatting, the pages fill up. When the notebook is nearly full, the AI starts struggling to remember what you said earlier. It gives vague answers, contradicts itself, or forgets things you told it 20 minutes ago.

Bannin tracks how full that notebook is. Below 50% -- you're fine. Above 75% -- things start getting flaky. Above 90% -- the conversation is on life support.

**2. Responses get slower (Latency Health)**

When you first start a chat, the AI responds in 1-2 seconds. As the conversation gets longer, the AI has to re-read everything from the beginning each time you send a message. A conversation that started at 1 second per response might be taking 4-5 seconds by message 50. It's like waiting longer and longer for a friend to text back -- a sign the conversation is getting stale.

Bannin times every response. If the second half of your conversation is noticeably slower than the first half, Bannin flags it.

**3. You pay more for less (Cost Efficiency)**

For developers using AI APIs, longer conversations cost more per response because the AI processes all the previous messages every time. You might be paying 3x per message compared to the start of the conversation, and getting worse quality in return. Bannin catches this trend.

**The Health Score: One Number, 0-100**

Bannin combines all three signals into a single number:

| Score | Rating | What it means | What Bannin tells you |
|---|---|---|---|
| 90-100 | Excellent | Fresh conversation, fast responses | "Your conversation is healthy." |
| 70-89 | Good | Working fine, some wear showing | "Still going strong." |
| 50-69 | Fair | Starting to degrade | "This conversation is getting long. Consider starting fresh soon." |
| 30-49 | Poor | Noticeably worse quality | "Consider starting a new conversation for better performance." |
| 0-29 | Critical | Severely degraded | "This conversation is severely degraded. Start a new chat immediately." |

**What happens when health drops?**

Eventually, Bannin will offer to help you start fresh without losing context. It captures the key points from your current conversation -- what you're working on, what decisions were made, what's still in progress -- and carries them into the new chat. Fresh conversation speed, but with the memory of the old one. Like transferring your call to a colleague who already has your file open.

This is the "Context Transfer" feature. It's the thing nobody else does. Token counters show a number. Bannin solves the actual problem.

---

## Idea: Logstache - Activity History

**What it is**: A searchable log of everything Bannin has observed on your system. Not a full integration with external tools -- just an internal history.

**The problem**: Right now, Bannin shows you what's happening *now*. But sometimes you want to know "what happened while I was away?" or "when did my RAM spike last?" Currently, the 30-minute ring buffer is the only memory, and it's gone when you restart.

**What it would look like**:
- Persistent log file (or lightweight SQLite database) that stores:
  - Every alert that fired (timestamp, severity, message, value)
  - Key metric snapshots (periodic summaries, not every 2-second reading)
  - Session start/stop events
  - Platform events (Colab session started, GPU reassigned, quota warning)
  - LLM usage summaries (per-session cost, tokens, health score changes)
- Simple search/filter: "show me all critical alerts from the last 3 days"
- Exportable: dump to JSON or CSV
- Dashboard page: "Activity" tab with a timeline view

**Why it matters**: When you walk away and come back, you want to know what happened. "Did anything go wrong?" "How much did my API calls cost while the script ran overnight?" "When did Colab restart my session?" This is the "you hit run, you walk away, then what?" answer in history form.

**When**: After Phase 3 (needs the core product stable first). Could be a pre-Phase 4 addition since it's local-only and doesn't need the relay server.

---

## Idea: Ollama & Local LLM Monitoring

**What it is**: Monitor locally-running LLMs through Ollama, llama.cpp, LM Studio, and similar tools.

**The problem**: More and more people run LLMs on their own machines. A Llama 3 model on Ollama uses 4-16 GB of RAM and hammers the GPU. But there's no easy way to see: "How much of my machine is this model eating?" "Is inference getting slower?" "How many tokens have I generated today?"

**What Bannin could track**:
- **Ollama-specific**: detect running Ollama instances, track which model is loaded, VRAM usage per model, inference speed (tokens/sec), total tokens generated per session
- **System impact**: how much CPU/RAM/GPU the local LLM is consuming vs. everything else
- **Health scoring**: same concept as API health -- is inference speed dropping? Is VRAM about to overflow?
- **Model switching**: detect when you switch models (loading a 70B after running a 7B) and warn about resource impact

**How it would work**:
- Ollama has a REST API at `localhost:11434` -- Bannin can query it for model info, running status
- For llama.cpp / LM Studio, detect the process and monitor resource usage
- Integrate into the same dashboard: "Local LLMs" section alongside system metrics
- MCP: Claude Code could ask "what local model is running and how much VRAM is it using?"

**Why it matters**: Local LLM users are exactly Bannin's audience -- technical people who care about their machine's health. Ollama has millions of downloads. Nobody monitors the resource impact of these models well. This is a natural extension of "Bannin watches everything you run."

**When**: Could slot in alongside Phase 3 or Phase 4. The Ollama API integration is straightforward. Main work is process detection and dashboard integration.

---

## Idea: DOM Auto-Update System (Browser Extension)

**What it is**: A remote configuration system for browser extension selectors, so the extension doesn't break every time ChatGPT/Claude.ai/Gemini updates their UI.

**The problem**: Web UIs change their HTML structure frequently. ChatGPT changes CSS class names regularly, Claude.ai uses randomized/obfuscated class names, Gemini uses Shadow DOM. Any hardcoded selector will eventually break. Normal Chrome extensions need a full update (code change, Chrome Web Store review, 1-3 day wait) to fix a broken selector. Users suffer in the meantime.

**The solution**: A `dom_selectors.json` config file (hosted on GitHub, same pattern as our platform limits config) that the extension fetches on startup:

```json
{
  "chatgpt": {
    "version": "2026-02-20",
    "message_turn": "article[data-testid^='conversation-turn-']",
    "message_id": "[data-message-id]",
    "author_role": "[data-message-author-role]",
    "input_field": "textarea#prompt-textarea",
    "streaming_class": "result-streaming",
    "api_intercept": "/backend-api/conversation/",
    "fallbacks": { ... }
  },
  "claude": { ... },
  "gemini": { ... }
}
```

- Extension fetches this daily (with 24-hour cache)
- If a selector breaks, we update the JSON on GitHub -- every user gets the fix within a day
- No Chrome Web Store review needed
- Bundled defaults as fallback (works offline)
- Extension validates selectors on page load and reports which ones work/fail

**When**: Part of Phase 4 (Browser Extension). This should be built into the extension architecture from the start, not bolted on later.

---

## Idea: Browser Extension - ChatGPT / Claude.ai / Gemini

**What it is**: Chrome extension (Manifest V3) that monitors your AI conversations in the browser. This is the biggest audience unlock -- every AI user, no Python needed.

**Key DOM research findings** (Feb 2026):

### ChatGPT
- Best approach: **intercept `/backend-api/conversation/` fetch responses** for exact data (tokens, timestamps, model). DOM parsing is the fallback.
- Stable selectors: `article[data-testid^="conversation-turn-"]`, `[data-message-id]`, `[data-message-author-role]`, `textarea#prompt-textarea`
- Streaming detection: `MutationObserver` watching for `result-streaming` class removal
- No timestamps or token counts visible in DOM -- must intercept API
- Strict CSP: all assets must be bundled locally

### Claude.ai
- **Randomized class names** -- class-based selectors completely unusable
- Input: ProseMirror `contenteditable` div, not a textarea
- Best approach: intercept **SSE streams** for usage data
- Use ARIA attributes and `data-testid` for UI targeting

### Gemini
- Uses **Shadow DOM** for some components -- must pierce shadow boundaries
- Angular/Lit framework with Material Design `mat-*` attributes
- Input: Quill editor `.ql-editor[contenteditable="true"]`
- Least documented ecosystem of the three

**When**: Phase 4, after PyPI launch. The DOM auto-update system above is built as part of this.

---

## Phase Order Reminder

1. **Phase 3** (NOW): LLM Health Exposure + PyPI Launch
2. **Phase 4**: Browser Extension (Chrome -- ChatGPT/Claude.ai/Gemini)
3. **Phase 5**: Connectivity (relay server, auth, WebSocket, push notifications)
4. **Phase 6**: Phone App + Actions + Polish

Logic: users first, infrastructure second. Don't build plumbing before you have people who want the water.

---

## Quick Ideas (Unscoped)

- **VS Code extension**: sidebar panel with Bannin metrics (demand-dependent, Phase 6+)
- **Slack/Discord bot alerts**: for teams (needs relay server, Phase 5+)
- **Apple Silicon GPU monitoring**: via macmon (Phase 6)
- **Cost budgets**: "Alert me when I spend more than $10 today across all LLMs"
- **Multi-machine view**: see all your machines in one dashboard (needs relay, Phase 5+)
- **Conversation depreciation curve**: visual graph of health score over time per conversation
