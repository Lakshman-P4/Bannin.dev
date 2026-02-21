# Try Bannin with Claude Code

Bannin (番人, Japanese for "watchman") monitors your system health while you work. It tracks CPU, RAM, disk, running processes, predicts out-of-memory crashes, fires smart alerts, and gives you a plain-English summary of how your computer is doing.

With Claude Code, Bannin works as an **MCP server** -- meaning Claude can check your system health, see what's running, and predict memory issues through natural conversation. You just ask.

**Tagline**: *I watch so you don't have to.*

**This is an early build.** Core monitoring, intelligence, conversation health tracking, and activity logging are working. Phone alerts and browser extension are coming. Looking for honest feedback.

Takes about 5 minutes to set up.

> **Using a different tool?** We have guides for every setup:
> - [VS Code / Cursor / Windsurf / JetBrains](trial-vscode.md) -- AI editors with MCP support
> - [Google Colab / Kaggle](trial-colab.md) -- cloud notebooks
> - [PowerShell / Terminal](trial-powershell.md) -- command line only, no IDE needed

---

## What you'll get

Once set up, you can ask Claude things like:

- "How's my system doing right now?"
- "What's eating my RAM?"
- "Am I going to run out of memory?"
- "Any alerts I should know about?"

Claude will call Bannin's tools and answer in plain English. No dashboards to check, no tabs to open -- just ask.

You also get a **live dashboard** in your browser at `http://localhost:8420` with real-time charts, process monitoring, and alerts.

---

## Step 1: Clone the repo

Open your terminal and run:

```
git clone https://github.com/Lakshman-P4/Bannin.dev.git
cd Bannin.dev
```

You should see the project files downloaded. If you get a "repository not found" error, you need collaborator access -- ask me to add you.

---

## Step 2: Install Bannin

**Mac / Linux:**
```
pip3 install -e .
```

**Windows:**
```
pip install --user -e .
```

This installs Bannin from the source code you just cloned. It should take about 10-15 seconds.

> **What does `-e .` mean?** It installs Bannin in "editable" mode from the current folder. This means if I update the code and you pull the latest changes, you automatically get the updates without reinstalling.

If you see a permissions error on Windows, the `--user` flag should fix it. On Mac, try `pip3` instead of `pip`.

---

## Step 3: Create the MCP config file

Claude Code needs a small config file to know about Bannin. You need to create this file in **whatever project folder you use Claude Code in**.

**3a.** Open the folder where you normally run Claude Code. For example:

```
cd ~/my-project
```

**3b.** Create a file called `.mcp.json` in that folder. Here's what goes inside:

**Mac / Linux:**
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

**Windows:**
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

> **Important:** The file name starts with a dot (`.mcp.json`). On Mac, files starting with a dot are hidden by default. You can create it from the terminal:
> ```
> # Mac/Linux:
> nano .mcp.json
> # paste the JSON above, save with Ctrl+O, exit with Ctrl+X
>
> # Windows (PowerShell):
> notepad .mcp.json
> # paste the JSON above, save, close
> ```

---

## Step 4: Start Claude Code

Open your terminal, navigate to the project folder where you put `.mcp.json`, and start Claude Code:

```
cd ~/my-project
claude
```

Claude Code reads `.mcp.json` on startup and automatically connects to Bannin. You don't need to do anything else -- it just works.

---

## Step 5: Verify it's connected

Once Claude Code is running, type:

```
/mcp
```

You should see **"bannin"** listed with **9 tools**, all showing as connected:

| Tool | What it does |
|---|---|
| `get_system_metrics` | CPU, RAM, disk, network, GPU usage |
| `get_running_processes` | What's using your resources (friendly names like "Google Chrome" instead of chrome.exe) |
| `predict_oom` | Will you run out of memory? Predicts crashes before they happen |
| `get_training_status` | Progress on long-running tasks (training, builds) |
| `get_active_alerts` | Anything that needs your attention right now |
| `check_context_health` | How healthy is this conversation? Detects context degradation and session fatigue |
| `get_recommendations` | Smart suggestions based on system state, LLM health, and platform constraints |
| `query_history` | Search past events, alerts, and snapshots ("what happened while I was away?") |
| `search_events` | Full-text search across all stored Bannin events |

**If bannin isn't listed:** Make sure `.mcp.json` is in the project root (not a subfolder). Try restarting Claude Code.

---

## Step 6: Try it out

Now just talk to Claude naturally. Here are some things to try:

### Basic health check

Ask:
> "How's my system doing right now?"

Claude calls `get_system_metrics` and tells you something like:

*"Your CPU is at 25%, RAM is at 93% (7.3 GB of 7.8 GB) -- memory is getting tight. Disk is at 79%. Network looks normal."*

### See what's running

Ask:
> "What's using the most resources on my machine?"

You'll see friendly names instead of cryptic process names:

*"Google Chrome (Browser) x26 -- 39.9% CPU, 1020 MB memory. VS Code (Code Editor) x8 -- 12.3% CPU, 450 MB. Memory Compression (System) -- 1.6 GB."*

### Memory prediction

Ask:
> "Am I going to run out of memory?"

Bannin analyzes your memory usage trend over time and tells you:

*"Memory is stable at 72%. No risk of running out."*

Or if things are getting tight:

*"RAM is growing at 1.2% per minute. At this rate, you'll run out in approximately 23 minutes. Confidence: 84%."*

### Check alerts

Ask:
> "Are there any active alerts?"

If something's wrong:

*"1 active alert: RAM HIGH -- 92% used (7.1 GB of 7.8 GB). Consider closing some applications."*

If everything's fine:

*"No active alerts. Your system looks healthy."*

> **Tip:** Alerts are live -- they only appear when the condition is actually happening right now. If RAM drops back to normal, the alert disappears on its own.

---

## Step 7: Open the live dashboard (optional)

Want a visual view? Open a **separate terminal** (keep Claude Code running in the first one) and start the dashboard:

**Mac / Linux:**
```
python3 -m bannin.cli start
```

**Windows:**
```
python -m bannin.cli start
```

Now open your browser and go to:

```
http://localhost:8420
```

You'll see:

- **Loading animation** -- Bannin's eye opening (takes a few seconds on first load)
- **Live CPU, RAM, disk gauges** with the top consumers listed under each
- **Process table** with friendly names and category badges (Browser, Code Editor, System, etc.)
- **Conversation health** -- real-time context freshness, session fatigue, and chat quality for your AI coding tool sessions
- **Alerts banner** at the top (only appears when something is actually wrong)
- **"See Summary" button** -- click it for a plain-English health report
- **"Ask Bannin" chatbot** -- type natural language questions about your system health
- **Memory chart** -- tracks RAM usage over time so you can spot trends
- **OOM prediction** -- shows if memory is growing and when it might run out
- **Task tracking** -- progress bars for any long-running operations

> **The MCP server and dashboard can run at the same time.** They don't conflict. Claude Code uses the MCP connection while the dashboard uses the HTTP API -- both talk to the same Bannin agent.

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
    # Check localhost:8420 -- the LLM Usage card shows live tracking
```

Skip this section if you don't have API keys -- system monitoring works perfectly without it.

---

## Troubleshooting

**"repository not found" when cloning:**
The repo is private. Ask me (Lakshman) to add you as a collaborator on GitHub, or I can send you a zip file.

**Port already in use (error 10048 or "address already in use"):**
Another Bannin instance is running. Find and kill it:
```
# Mac/Linux:
lsof -i :8420
kill -9 <PID>

# Windows PowerShell:
netstat -ano | findstr :8420
taskkill /PID <PID> /F
```

**Dashboard shows "--" for everything:**
Wait 10-15 seconds. The process scanner needs time for its first pass, especially on Windows. You'll see a "Scanning processes..." spinner until it's ready.

**MCP server not connecting:**
1. Run `/mcp` in Claude Code to check
2. Make sure `.mcp.json` is in the project root (not a subfolder)
3. Make sure you used `python3` (Mac) or `python` (Windows) in the config
4. Try restarting Claude Code completely

**"No module named bannin":**
The install didn't work. Go back to Step 2 and try again. On Windows, make sure you include `--user`. On Mac, use `pip3`.

---

## What's coming next

- **Browser extension** -- monitors ChatGPT, Claude.ai, Gemini directly in your browser
- **Phone alerts** -- push notifications when something needs your attention
- **Auto-actions** -- Bannin takes action on your behalf (e.g., save checkpoints before a crash)

---

## Feedback

After trying it, I'd love to know:

- Did the install work smoothly?
- Is this useful during your coding sessions?
- What would make you actually keep this running?
- What's missing?

Be brutally honest -- "I didn't find this useful because X" is more helpful than "looks cool!"
