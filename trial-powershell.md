# Try Bannin from the Terminal (PowerShell, Bash, or any command line)

Bannin (番人, Japanese for "watchman") monitors your system health while you work. It tracks CPU, RAM, disk, running processes, predicts out-of-memory crashes, fires smart alerts, and gives you a plain-English summary of how your computer is doing.

This guide is for people who prefer the command line. No IDE, no browser extension, no special tools -- just your terminal and `curl`.

**Tagline**: *I watch so you don't have to.*

**This is an early build.** Core monitoring and intelligence are working. Phone alerts, browser extension, and conversation health tracking are coming. Looking for honest feedback.

Takes about 5 minutes to set up.

> **Using a different tool?** We have guides for every setup:
> - [Claude Code](trial.md) -- Claude's CLI coding tool
> - [VS Code / Cursor / Windsurf / JetBrains](trial-vscode.md) -- AI editors with MCP support
> - [Google Colab / Kaggle](trial-colab.md) -- cloud notebooks

---

## What you'll get

After setup, Bannin runs a small server on your machine at `http://localhost:8420`. You can query it with `curl` (or any HTTP tool) to get:

- **System metrics** -- CPU, RAM, disk, network, GPU usage
- **Running processes** -- what's using your resources, with friendly names
- **OOM prediction** -- will you run out of memory?
- **Active alerts** -- anything that needs attention right now
- **Plain-English summary** -- "Your computer is healthy" or "Memory is getting tight"
- **Live dashboard** -- open `http://localhost:8420` in any browser for real-time charts

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

**Windows (PowerShell):**
```
pip install --user -e .
```

This installs Bannin from the source code you just cloned. Takes about 10-15 seconds.

> **What does `-e .` mean?** It installs Bannin in "editable" mode. If I push updates and you pull, you get them automatically without reinstalling.

If you see a permissions error on Windows, the `--user` flag should fix it. On Mac, use `pip3` instead of `pip`.

---

## Step 3: Start the Bannin agent

Open a terminal window and run:

**Mac / Linux:**
```
python3 -m bannin.cli start
```

**Windows (PowerShell):**
```
python -m bannin.cli start
```

You should see output like:

```
Starting Bannin agent...
Bannin agent running at http://localhost:8420
```

**Leave this terminal running.** Bannin needs to stay alive to collect metrics. Open a **new/second terminal** for the next steps.

> **Why `python -m bannin.cli start` instead of just `bannin start`?** On some systems, the `bannin` command isn't on your PATH after install. Using `python -m` always works.

---

## Step 4: Verify it's running

In your **new terminal**, run:

**Mac / Linux / Windows (PowerShell):**
```
curl http://localhost:8420/health
```

You should see:

```json
{"status": "ok"}
```

If you see this, Bannin is running and ready. If you get "connection refused", go back and make sure Step 3 is still running in the other terminal.

> **Windows note:** `curl` works in PowerShell out of the box. If you're using old Command Prompt (cmd.exe), you might need to use `curl.exe` instead of `curl`.

---

## Step 5: Try the API endpoints

Here's what you can ask Bannin. Run these in your second terminal one at a time.

### System metrics (CPU, RAM, disk, network)

```
curl http://localhost:8420/metrics
```

**Example output:**
```json
{
  "cpu": {
    "percent": 24.5,
    "count": 8
  },
  "memory": {
    "total_gb": 7.8,
    "used_gb": 6.2,
    "available_gb": 1.6,
    "percent": 79.5
  },
  "disk": {
    "total_gb": 476.3,
    "used_gb": 312.1,
    "free_gb": 164.2,
    "percent": 65.5
  }
}
```

**What this tells you:** Your CPU is at 24.5% (fine), RAM is at 79.5% (getting busy), and disk is at 65.5% (plenty of room).

---

### Running processes (friendly names)

```
curl http://localhost:8420/processes
```

**Example output:**
```json
{
  "top_processes": [
    {
      "name": "Google Chrome",
      "category": "Browser",
      "cpu_percent": 39.9,
      "memory_mb": 1020.3,
      "instance_count": 26
    },
    {
      "name": "VS Code",
      "category": "Code Editor",
      "cpu_percent": 12.3,
      "memory_mb": 450.1,
      "instance_count": 8
    },
    {
      "name": "Memory Compression",
      "category": "System",
      "cpu_percent": 0.0,
      "memory_mb": 1623.5,
      "instance_count": 1
    }
  ]
}
```

**What this tells you:** Chrome is your biggest resource consumer (26 instances using 1 GB of RAM). You might want to close some tabs.

---

### Plain-English summary

```
curl http://localhost:8420/summary
```

**Example output:**
```json
{
  "level": "busy",
  "headline": "Your computer is a little busy right now.",
  "details": "RAM is at 92% (7.1 GB of 7.8 GB). The biggest memory users are Memory Compression (1.6 GB), Google Chrome (871 MB).",
  "suggestions": ["Consider closing some Google Chrome tabs to free up memory."]
}
```

**What this tells you:** In plain English -- your computer is busy, RAM is the bottleneck, and Chrome is the culprit. Close some tabs.

---

### Active alerts

```
curl http://localhost:8420/alerts/active
```

**Example output (when something's wrong):**
```json
{
  "active": [
    {
      "severity": "warning",
      "message": "RAM HIGH - 92% used (7.1 GB of 7.8 GB)"
    }
  ],
  "count": 1
}
```

**Example output (when everything's fine):**
```json
{
  "active": [],
  "count": 0
}
```

**What this tells you:** If the list is empty, you're good. If there are alerts, they tell you exactly what's wrong and how bad it is.

> **Alerts are live.** They only appear when the condition is actually true right now. If RAM drops back to normal, the alert disappears automatically.

---

### OOM prediction (will you run out of memory?)

```
curl http://localhost:8420/predictions/oom
```

**Example output (stable):**
```json
{
  "ram": {
    "trend": "stable",
    "current_percent": 72.3,
    "message": "Memory stable"
  }
}
```

**Example output (warning):**
```json
{
  "ram": {
    "trend": "increasing",
    "current_percent": 88.5,
    "growth_rate_per_min": 1.2,
    "minutes_until_full": 9.6,
    "confidence_percent": 84,
    "message": "OOM predicted in ~10 minutes"
  }
}
```

**What this tells you:** Bannin tracks memory over time. If it's growing, it tells you how fast and when you'll crash. This is the feature Colab and Kaggle don't have -- you get a warning BEFORE the crash, not after.

> **Note:** OOM predictions need about 30 seconds of data collection before they work. If you just started the agent, the first prediction might say "not enough data yet."

---

### All endpoints at a glance

| Endpoint | What it returns |
|---|---|
| `curl http://localhost:8420/health` | `{"status": "ok"}` -- is Bannin running? |
| `curl http://localhost:8420/metrics` | CPU, RAM, disk, network, GPU |
| `curl http://localhost:8420/processes` | Top processes with friendly names |
| `curl http://localhost:8420/summary` | Plain-English health summary |
| `curl http://localhost:8420/alerts/active` | Current warnings and alerts |
| `curl http://localhost:8420/predictions/oom` | Memory crash prediction |
| `curl http://localhost:8420/status` | Agent identity (hostname, OS, version, uptime) |
| `curl http://localhost:8420/tasks` | Progress on tracked tasks (training runs, etc.) |

---

## Step 6: Open the live dashboard (optional)

Want a visual view instead of JSON? Just open this URL in any browser:

```
http://localhost:8420
```

**From PowerShell:**
```powershell
Start-Process http://localhost:8420
```

**From Mac/Linux terminal:**
```
open http://localhost:8420
```

You'll see:

- **Loading animation** -- Bannin's eye opening
- **Live CPU, RAM, disk gauges** with the top consumers listed under each
- **Process table** with friendly names and category badges (Browser, Code Editor, System, etc.)
- **Alerts banner** at the top (only appears when something is wrong)
- **"See Summary" button** -- click for a plain-English health report
- **Memory chart** -- tracks RAM usage over time so you can spot trends
- **OOM prediction** -- shows if memory is growing and when it might run out
- **Task tracking** -- progress bars for long-running operations

The dashboard updates in real time. Leave it open in a tab and glance at it whenever you want.

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

Skip this if you don't have API keys -- system monitoring works without it.

---

## Troubleshooting

**"repository not found" when cloning:**
The repo is private. Ask me (Lakshman) to add you as a collaborator on GitHub, or I can send you a zip file.

**"Connection refused" when using curl:**
The Bannin agent isn't running. Go back to Step 3 and start it. Make sure you leave that terminal open.

**Port already in use (error 10048 or "address already in use"):**
Another Bannin instance is already running on port 8420. Find and kill it:
```
# Mac/Linux:
lsof -i :8420
kill -9 <PID>

# Windows PowerShell:
netstat -ano | findstr :8420
taskkill /PID <PID> /F
```

Then try starting again.

**Dashboard shows "--" for everything:**
Wait 10-15 seconds. The process scanner needs time for its first pass, especially on Windows. You'll see a "Scanning processes..." spinner until it's ready.

**"No module named bannin":**
The install didn't work. Go back to Step 2 and try again. On Windows, make sure you include `--user`. On Mac, use `pip3`.

**curl returns garbled text on Windows:**
If you're using old Command Prompt (cmd.exe), try PowerShell instead. Or use `curl.exe` instead of `curl`.

---

## What's coming next

- **Conversation health scoring** -- detects when AI conversations are degrading and recommends starting fresh
- **Browser extension** -- monitors ChatGPT, Claude.ai, Gemini directly in your browser
- **Activity logging** -- searchable history of everything Bannin has observed
- **Phone alerts** -- push notifications when something needs your attention

---

## Feedback

After trying it, I'd love to know:

- Did the install and setup work smoothly?
- Is the terminal API useful? Or do you prefer the dashboard?
- What would make you actually keep Bannin running?
- What's missing?

Be brutally honest -- "I didn't find this useful because X" is more helpful than "looks cool!"
