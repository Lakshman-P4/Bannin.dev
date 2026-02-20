# Try Bannin

Bannin (番人, Japanese for "watchman") monitors your system health while you work. It tracks CPU, RAM, disk, running processes (with friendly names like "Google Chrome" instead of chrome.exe), predicts out-of-memory crashes, fires smart alerts, and gives you a plain-English summary of how your computer is doing. It works inside Claude Code as an MCP server, or as a live dashboard in your browser.

**Tagline**: *I watch so you don't have to.*

**This is an early build.** The core monitoring and intelligence engine is working. Features like phone alerts, a browser extension for ChatGPT/Claude.ai, and conversation health tracking are coming. I'm looking for honest feedback on what's here.

Takes about 5 minutes to set up.

---

## Step 1 - Clone the repo

Open your terminal and run:

```
git clone https://github.com/Lakshman-P4/Bannin.dev.git
cd Bannin.dev
```

## Step 2 - Install it

**Mac:**
```
pip3 install -e .
```

**Windows:**
```
pip install --user -e .
```

If you see a permissions error, add `--user` to the command.

---

## Option A: Claude Code Users (MCP Server)

This lets Claude Code check your system health, see what's running, predict memory issues, and more - all through natural conversation.

### Step 3 - Add the MCP config

In whatever project folder you use Claude Code in, create a file called `.mcp.json`:

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

> **Windows users**: change `python3` to `python`

### Step 4 - Open Claude Code

Start Claude Code in that project like you normally do. It should automatically detect and connect to Bannin.

### Step 5 - Verify it's connected

Type `/mcp` in Claude Code. You should see "bannin" listed with 5 tools:

- `get_system_metrics` - CPU, RAM, disk, network, GPU
- `get_running_processes` - what's using your resources (friendly names)
- `predict_oom` - will you run out of memory?
- `get_training_status` - progress on long-running tasks
- `get_active_alerts` - anything that needs attention right now

### Step 6 - Try it out

Ask Claude Code things like:

**Basic health check:**
> "How's my system doing right now?"

Claude will call `get_system_metrics` and tell you something like: "Your CPU is at 25%, RAM is at 93% (7.3 GB of 7.8 GB) - memory is getting tight. Disk is at 79%."

**See what's running:**
> "What's using the most resources on my machine?"

You'll see friendly names: "Google Chrome (Browser) x26 - 39.9% CPU, 1020 MB" instead of raw `chrome.exe` entries.

**Memory prediction:**
> "Am I going to run out of memory?"

Bannin will analyze your memory usage trend and tell you if OOM is likely, with confidence percentage and time estimate.

**Check alerts:**
> "Are there any active alerts?"

Shows current warnings like "RAM HIGH: 92% used" - but only if the condition is still true right now (alerts disappear when the problem goes away).

### Want the dashboard too?

Open a separate terminal and run:

**Mac:**
```
python3 -m bannin.cli start
```

**Windows:**
```
python -m bannin.cli start
```

Then open `http://localhost:8420` in your browser. You'll see:
- A loading animation (Bannin's eye opening)
- Live CPU, RAM, disk with top consumers under each
- Process table with friendly names and category badges
- Alerts banner (only when something is wrong)
- "See Summary" button for a plain-English health report
- Memory usage chart over time
- OOM predictions and task tracking

The MCP server and dashboard can run at the same time - they don't conflict.

---

## Option B: VS Code / Any Editor Users (Dashboard Only)

### Step 3 - Start Bannin

Open a terminal and run:

**Mac:**
```
python3 -m bannin.cli start
```

**Windows:**
```
python -m bannin.cli start
```

You should see:
```
Bannin agent v0.1.0
Dashboard: http://127.0.0.1:8420
API docs:  http://127.0.0.1:8420/docs
```

### Step 4 - Open the dashboard

Go to `http://localhost:8420` in your browser.

Wait for Bannin's eye to open (the loading animation), then you'll see the full dashboard with live metrics updating every few seconds.

### Step 5 - Try the summary

Click "See Summary" on the dashboard. You'll get a plain-English report like:

> **Your computer is a little busy right now.**
> RAM is at 85%. The biggest memory users are Google Chrome (1.0 GB), Claude Desktop (773 MB), Memory Compression (1.6 GB).
> *Suggestion: Consider closing some Google Chrome tabs to free up memory.*

---

## Optional: LLM API Tracking

If you use OpenAI, Anthropic, or Google APIs in your own code, Bannin can track tokens, cost, latency, and context window health:

```python
import bannin
from openai import OpenAI  # or anthropic, google, etc.

client = bannin.wrap(OpenAI())

with bannin.watch():
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}]
    )
    # Check localhost:8420 - the LLM Usage card shows live tracking
```

Skip this section if you don't have API keys - system monitoring works without it.

---

## Troubleshooting

**Port already in use (error 10048):**
Another Bannin instance is running. Find and kill it:
```
# Mac/Linux:
lsof -i :8420
kill -9 <PID>

# Windows:
netstat -ano | findstr :8420
taskkill /PID <PID> /F
```

**Dashboard shows "--" for everything:**
Wait 10-15 seconds. The process scanner needs time for its first pass, especially on Windows. You'll see a "Scanning processes..." spinner until it's ready.

**MCP server not connecting in Claude Code:**
Run `/mcp` to check. If bannin isn't listed, make sure `.mcp.json` is in the project root (not a subfolder). Try restarting Claude Code.

---

## What's coming next

- **Conversation health scoring** - detects when AI conversations are degrading and recommends starting fresh
- **Browser extension** - monitors ChatGPT, Claude.ai, Gemini directly in your browser
- **Activity logging** - searchable history of everything Bannin has observed
- **Phone alerts** - push notifications when something needs your attention

---

## Feedback

After trying it, I'd love to know:

- Did the install work smoothly?
- Is this useful during your coding sessions?
- What would make you actually keep this running?
- What's missing?

Be brutally honest - "I didn't find this useful because X" is more helpful than "looks cool!"
