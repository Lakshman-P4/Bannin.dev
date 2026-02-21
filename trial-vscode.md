# Try Bannin with VS Code, Cursor, Windsurf, or Other Editors

Bannin (番人, Japanese for "watchman") monitors your system health while you work. It tracks CPU, RAM, disk, running processes, predicts out-of-memory crashes, fires smart alerts, and gives you a plain-English summary of how your computer is doing.

This guide sets up Bannin as an **MCP server** inside your code editor. That means you can ask your AI assistant (Copilot, Cursor AI, Windsurf AI, etc.) about your system health directly in the chat -- while you keep coding.

**Tagline**: *I watch so you don't have to.*

**This is an early build.** Core monitoring, intelligence, conversation health tracking, and activity logging are working. Phone alerts and browser extension are coming. Looking for honest feedback.

Takes about 5-10 minutes to set up.

> **Using a different tool?** We have guides for every setup:
> - [Claude Code](trial.md) -- Claude's CLI coding tool
> - [Google Colab / Kaggle](trial-colab.md) -- cloud notebooks
> - [PowerShell / Terminal](trial-powershell.md) -- command line only, no IDE needed

---

## Which editors does this work with?

Any editor that supports **MCP (Model Context Protocol)** servers. As of February 2026, that includes:

| Editor | AI Assistant | MCP Support |
|---|---|---|
| **VS Code** | GitHub Copilot Chat | Built-in (Agent mode) |
| **Cursor** | Cursor AI | Built-in |
| **Windsurf** | Windsurf AI (Codeium) | Built-in |
| **Zed** | Zed AI | Built-in |
| **JetBrains IDEs** (IntelliJ, PyCharm, WebStorm, etc.) | JetBrains AI / Copilot | MCP plugin available |

> **Not sure if your editor supports MCP?** Check your editor's settings for "MCP" or "Model Context Protocol". If you see a way to add MCP servers, it works.

---

## What you'll get

Once set up, you can ask your AI assistant things like:

- "How's my system doing right now?"
- "What's eating my RAM?"
- "Am I going to run out of memory?"
- "Any alerts I should know about?"

Your AI calls Bannin's tools and answers in plain English -- right in the chat panel while you code.

You also get a **live dashboard** in your browser at `http://localhost:8420` with real-time charts, process monitoring, and alerts.

---

## Step 1: Clone the repo

Open your terminal and run:

```
git clone https://github.com/Lakshman-P4/Bannin.dev.git
cd Bannin.dev
```

You should see the project files downloaded. If you get a "repository not found" error, you need collaborator access -- ask me to add you.

**Remember where you cloned it.** You'll need this path later. For example:
- **Mac/Linux:** `/Users/yourname/Bannin.dev`
- **Windows:** `C:\Users\yourname\Documents\Bannin.dev`

---

## Step 2: Install Bannin

Stay in the `Bannin.dev` folder and run:

**Mac / Linux:**
```
pip3 install -e .
```

**Windows:**
```
pip install --user -e .
```

This installs Bannin from the source code you just cloned. Takes about 10-15 seconds.

> **What does `-e .` mean?** It installs Bannin in "editable" mode. If I update the code and you pull changes, you get the updates automatically without reinstalling.

---

## Step 3: Find your Python path

Before configuring your editor, you need to know where Python is installed.

**Mac / Linux:**
```
which python3
```
This usually returns something like `/usr/bin/python3` or `/usr/local/bin/python3`.

**Windows (PowerShell):**
```
where python
```
This usually returns something like `C:\Python311\python.exe` or `C:\Users\yourname\AppData\Local\Programs\Python\Python311\python.exe`.

Write this path down -- you'll use it in the next step.

---

## Step 4: Add Bannin to your editor

Pick your editor below and follow the instructions.

### VS Code (GitHub Copilot)

You have two options: **global** (works in every project you open) or **per-project** (only works in one folder).

#### Option A: Global setup (recommended)

This makes Bannin available in every project you open in VS Code.

**4a.** Open VS Code.

**4b.** Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac) to open the Command Palette.

**4c.** Type `Preferences: Open User Settings (JSON)` and press Enter.

**4d.** Your `settings.json` file opens. Add this block inside the top-level `{ }` braces (if there's already content, add a comma after the last entry, then paste this):

**Mac / Linux:**
```json
"mcp": {
  "servers": {
    "bannin": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "bannin.mcp"],
      "env": {
        "PYTHONPATH": "/Users/yourname/Bannin.dev"
      }
    }
  }
}
```

**Windows:**
```json
"mcp": {
  "servers": {
    "bannin": {
      "type": "stdio",
      "command": "C:\\Python311\\python.exe",
      "args": ["-m", "bannin.mcp"],
      "env": {
        "PYTHONPATH": "C:\\Users\\yourname\\Documents\\Bannin.dev"
      }
    }
  }
}
```

> **Important:** Replace the paths with YOUR actual paths:
> - `command` should be the Python path from Step 3
> - `PYTHONPATH` should be where you cloned Bannin.dev in Step 1
> - On Windows, use double backslashes (`\\`) in paths

**4e.** Save the file (`Ctrl+S`).

#### Option B: Per-project setup

This only enables Bannin in one specific project folder.

**4a.** Open your project folder in VS Code.

**4b.** Create a folder called `.vscode` inside your project (if it doesn't exist already).

**4c.** Inside `.vscode`, create a file called `mcp.json` with this content:

**Mac / Linux:**
```json
{
  "servers": {
    "bannin": {
      "type": "stdio",
      "command": "python3",
      "args": ["-m", "bannin.mcp"],
      "env": {
        "PYTHONPATH": "/Users/yourname/Bannin.dev"
      }
    }
  }
}
```

**Windows:**
```json
{
  "servers": {
    "bannin": {
      "type": "stdio",
      "command": "C:\\Python311\\python.exe",
      "args": ["-m", "bannin.mcp"],
      "env": {
        "PYTHONPATH": "C:\\Users\\yourname\\Documents\\Bannin.dev"
      }
    }
  }
}
```

> **Replace the paths** with your actual Python path and Bannin.dev location, just like in Option A.

---

### Cursor

Cursor uses the same config format as VS Code.

**4a.** Open Cursor.

**4b.** Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac).

**4c.** Type `Preferences: Open User Settings (JSON)` and press Enter.

**4d.** Add the same `"mcp"` block from the VS Code section above (Option A).

**4e.** Save the file.

Alternatively, create `.cursor/mcp.json` in your project folder for per-project setup:

**Mac / Linux:**
```json
{
  "mcpServers": {
    "bannin": {
      "command": "python3",
      "args": ["-m", "bannin.mcp"],
      "env": {
        "PYTHONPATH": "/Users/yourname/Bannin.dev"
      }
    }
  }
}
```

**Windows:**
```json
{
  "mcpServers": {
    "bannin": {
      "command": "C:\\Python311\\python.exe",
      "args": ["-m", "bannin.mcp"],
      "env": {
        "PYTHONPATH": "C:\\Users\\yourname\\Documents\\Bannin.dev"
      }
    }
  }
}
```

---

### Windsurf

Windsurf (by Codeium) is a VS Code fork with built-in MCP support.

**4a.** Open Windsurf.

**4b.** Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).

**4c.** Type `Preferences: Open User Settings (JSON)` and press Enter.

**4d.** Add the same `"mcp"` block from the VS Code section above (Option A).

**4e.** Save the file.

Or create `.vscode/mcp.json` in your project folder -- same as the VS Code per-project option.

---

### Zed

**4a.** Open Zed.

**4b.** Open Settings (`Cmd+,` on Mac, or `Ctrl+,` on Linux).

**4c.** Add this to your settings:

```json
{
  "context_servers": {
    "bannin": {
      "command": {
        "path": "python3",
        "args": ["-m", "bannin.mcp"],
        "env": {
          "PYTHONPATH": "/Users/yourname/Bannin.dev"
        }
      }
    }
  }
}
```

> **Windows users:** change `python3` to your full Python path and update PYTHONPATH.

**4d.** Save and restart Zed.

---

### JetBrains (IntelliJ, PyCharm, WebStorm, etc.)

**4a.** Make sure you have the **MCP plugin** installed (Settings > Plugins > search "MCP").

**4b.** Go to Settings > Tools > MCP Servers.

**4c.** Click "+" to add a new server.

**4d.** Fill in:
- **Name:** `bannin`
- **Command:** `python3` (Mac/Linux) or `C:\Python311\python.exe` (Windows)
- **Arguments:** `-m bannin.mcp`
- **Environment:** Add `PYTHONPATH` = your Bannin.dev path

**4e.** Click OK and restart the IDE.

---

## Step 5: Reload your editor

After adding the config, your editor needs to reload to pick up the changes.

**VS Code / Cursor / Windsurf:**
Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) and type `Developer: Reload Window`. Press Enter.

**Zed:**
Close and reopen Zed.

**JetBrains:**
Close and reopen the IDE.

---

## Step 6: Verify it's connected

### VS Code (Copilot)

**6a.** Open Copilot Chat (click the Copilot icon in the sidebar, or press `Ctrl+Shift+I`).

**6b.** Make sure the chat is in **Agent** mode. Look at the dropdown at the top of the chat panel -- it should say "Agent" (not "Edit" or "Ask").

**6c.** Click the **tools icon** (wrench/hammer) in the chat input area. You should see **"bannin"** listed with **9 tools**, all showing green checkmarks:

- `get_system_metrics` -- CPU, RAM, disk, network, GPU
- `get_running_processes` -- what's using your resources
- `predict_oom` -- will you run out of memory?
- `get_training_status` -- progress on long-running tasks
- `get_active_alerts` -- anything that needs attention
- `check_context_health` -- how healthy is this conversation? Detects context degradation and session fatigue
- `get_recommendations` -- smart suggestions based on system state, LLM health, and platform constraints
- `query_history` -- search past events, alerts, and snapshots
- `search_events` -- full-text search across all stored Bannin events

### Cursor

Open the AI chat panel. Bannin's tools should appear when you click the tools/MCP icon. Ask "How's my system doing?" to test.

### Windsurf

Open Windsurf's AI chat. Type a question like "Check my system health" -- if Bannin is connected, it will call the tools automatically.

### Zed

Open the AI panel. Bannin should appear as a context server. Ask a question to verify.

### JetBrains

Open the AI chat or MCP panel. Check that bannin appears as a connected server.

---

## Step 7: Try it out

Now just ask your AI assistant naturally. Here are some things to try:

### Basic health check

Ask:
> "How's my system doing right now?"

Your AI calls Bannin and tells you something like:

*"Your CPU is at 25%, RAM is at 93% (7.3 GB of 7.8 GB) -- memory is getting tight. Disk is at 79%. Network looks normal."*

### See what's running

Ask:
> "What's using the most resources on my machine?"

You'll see friendly names instead of cryptic process names:

*"Google Chrome (Browser) x26 -- 39.9% CPU, 1020 MB memory. VS Code (Code Editor) x8 -- 12.3% CPU, 450 MB."*

### Memory prediction

Ask:
> "Am I going to run out of memory?"

*"Memory is stable at 72%. No risk of running out."*

Or if things are getting tight:

*"RAM is growing at 1.2% per minute. At this rate, you'll run out in approximately 23 minutes. Confidence: 84%."*

### Check alerts

Ask:
> "Are there any active alerts?"

*"1 active alert: RAM HIGH -- 92% used. Consider closing some applications."*

Or:

*"No active alerts. Your system looks healthy."*

---

## Step 8: Open the live dashboard (optional)

Want a visual view with charts and graphs? Open a **separate terminal** and start the dashboard:

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

- **Loading animation** -- Bannin's eye opening
- **Live CPU, RAM, disk gauges** with the top consumers listed under each
- **Process table** with friendly names and category badges
- **Conversation health** -- real-time context freshness, session fatigue, and chat quality for your AI coding tool sessions
- **Alerts banner** at the top (only when something is wrong)
- **"See Summary" button** -- click for a plain-English health report
- **"Ask Bannin" chatbot** -- type natural language questions about your system health
- **Memory chart** -- tracks usage over time
- **OOM prediction** -- shows if memory is growing and when it might run out

> **Your editor and the dashboard work at the same time.** They don't conflict. The AI chat uses the MCP connection while the dashboard uses the HTTP API -- both talk to the same Bannin agent.

---

## Optional: LLM API Tracking

If you use OpenAI, Anthropic, or Google APIs in your code, Bannin can track tokens, cost, latency, and context window health:

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

**"No module named bannin" error:**
Your editor can't find Bannin. This is usually a path issue. Double-check:
1. The `PYTHONPATH` in your config points to where you cloned Bannin.dev
2. The `command` points to the correct Python executable
3. You ran `pip install -e .` (or `pip install --user -e .` on Windows) inside the Bannin.dev folder

**Tools not showing up in the chat:**
1. Make sure you reloaded the editor after adding the config (Step 5)
2. For VS Code: make sure Copilot Chat is in **Agent** mode, not "Ask" or "Edit"
3. Try closing and reopening the editor completely

**Port already in use (when starting dashboard):**
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
Wait 10-15 seconds. The process scanner needs time for its first pass, especially on Windows.

---

## What's coming next

- **Browser extension** -- monitors ChatGPT, Claude.ai, Gemini directly in your browser
- **Phone alerts** -- push notifications when something needs your attention
- **Auto-actions** -- Bannin takes action on your behalf (e.g., save checkpoints before a crash)

---

## Feedback

After trying it, I'd love to know:

- Did the setup work in your editor?
- Is it useful to ask your AI about system health while coding?
- What would make you actually keep this running?
- What's missing?

Be brutally honest -- "I didn't find this useful because X" is more helpful than "looks cool!"
