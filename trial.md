# Try Bannin

Bannin (Japanese for "watchman") is a monitoring tool I'm building that watches your system health while you code. It tracks CPU, RAM, processes, predicts out-of-memory issues, and fires alerts when something needs attention. It works inside Claude Code, Cursor, and Windsurf as an MCP server, or as a live dashboard for VS Code users.

**This is an early build — Phases 1 and 2 of a larger project.** The core monitoring and intelligence engine is working, but features like phone alerts, a browser extension for ChatGPT/Claude.ai, and conversation health tracking are still coming. I'm looking for honest feedback on what's here so far.

Takes about 5 minutes to set up.

---

## Step 1 — Clone the repo

Open your terminal and run:

```
git clone https://github.com/Lakshman-P4/Bannin.dev.git
```

## Step 2 — Install it

```
cd Bannin.dev
pip install -e .
```

If you get a permissions error on Mac, try `pip install --user -e .`

---

## If you use Claude Code, Cursor, or Windsurf

### Step 3 — Add it to your project

In whatever project folder you use Claude Code in, create a file called `.mcp.json` with this:

```json
{
  "mcpServers": {
    "bannin": {
      "command": "python3",
      "args": ["-m", "bannin.mcp"]
    }
  }
}
```

Use `python3` on Mac, `python` on Windows.

### Step 4 — Open Claude Code in that project

Start Claude Code like you normally do. It should automatically connect to Bannin.

### Step 5 — Type `/mcp` to check it's connected

You should see "bannin" listed as a connected server.

### Step 6 — Try it out

Ask Claude Code any of these:

- "How's my system doing?"
- "What's using the most CPU right now?"
- "Are there any alerts?"
- "Predict if I'll run out of memory"

### Want the dashboard too?

You can run the dashboard alongside the MCP server — they don't conflict. Open a separate terminal and run:

```
python3 -m bannin.cli start
```

Then open `http://localhost:8420` in your browser. You'll have Claude Code querying Bannin via MCP AND the live visual dashboard running at the same time.

---

## If you use VS Code

### Step 3 — Start Bannin from your VS Code terminal

Open the terminal inside VS Code (`Ctrl+`` ` or `Cmd+`` `) and run:

```
python3 -m bannin.cli start
```

### Step 4 — Open the dashboard

Go to `http://localhost:8420` in your browser. You'll see a live dashboard showing your CPU, RAM, disk, running processes, alerts, and OOM predictions — all updating in real time while you code.

---

## Already have an OpenAI, Anthropic, or Google API key?

If you already use LLM APIs in your own code, Bannin can track your token usage, cost, latency, and context window health right now. Just wrap your client:

```python
import bannin
from openai import OpenAI  # or anthropic, google, etc.

client = bannin.wrap(OpenAI())

with bannin.watch():
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}]
    )
    # check localhost:8420 — the LLM Usage card will show live tracking
```

This is basic token and cost tracking. The bigger feature coming soon is **conversation health scoring** — Bannin will detect when your AI conversations are degrading and help you start fresh without losing context. If you don't have API keys, skip this — the system monitoring works without it.

---

## What's coming next

This is Phases 1-2 of a bigger project. What you're seeing now is the system monitoring and intelligence engine. Coming soon:

- **LLM conversation health tracking** — if you use OpenAI, Anthropic, or Google APIs in your code, Bannin will track token usage, cost, latency, and predict when your conversation is degrading
- **Browser extension** — monitors ChatGPT, Claude.ai, and Gemini in your browser. Detects when conversations are getting worse and helps you start fresh without losing context
- **Phone alerts** — push notifications when something needs your attention

---

## Feedback

After trying it, I'd love to know:

- Did the install work smoothly?
- Is this useful during your coding sessions?
- What would make you actually keep this running?
- What's missing?

Be brutally honest — "I didn't find this useful because X" is more helpful than "looks cool!"
