# Try Bannin on Cloud Notebooks (Google Colab, Kaggle, and more)

Bannin (番人, Japanese for "watchman") monitors your notebook session while you work. It tells you how much time you have left, whether your RAM is about to crash, if your GPU got reassigned, and whether your data is safe.

**One cell to install. No cloning, no accounts, no API keys.**

**Tagline**: *I watch so you don't have to.*

**This is an early build.** Core monitoring and intelligence are working. Phone alerts and auto-checkpoint are coming. Looking for honest feedback.

> **Using a different tool?** We have guides for every setup:
> - [Claude Code](trial.md) -- Claude's CLI coding tool
> - [VS Code / Cursor / Windsurf / JetBrains](trial-vscode.md) -- AI editors with MCP support
> - [PowerShell / Terminal](trial-powershell.md) -- command line only, no IDE needed

---

## Which cloud notebooks does this work with?

| Platform | Tested | What Bannin monitors |
|---|---|---|
| **Google Colab** | Verified on real platform | Session time, GPU type/reallocation, RAM, disk, Drive mount, tier detection |
| **Kaggle Notebooks** | Verified on real platform | Session time, GPU weekly quota, dual-GPU detection, output limits, internet access |
| **Paperspace Gradient** | Should work (psutil-based) | CPU, RAM, GPU, disk -- no platform-specific features yet |
| **Amazon SageMaker Studio** | Should work (psutil-based) | CPU, RAM, GPU, disk -- no platform-specific features yet |
| **Lightning AI** | Should work (psutil-based) | CPU, RAM, GPU, disk -- no platform-specific features yet |

> **Colab and Kaggle** get the full experience -- Bannin detects the platform automatically and shows specific info like session countdown, GPU quota, and storage warnings. Other platforms get the core monitoring (CPU, RAM, GPU, OOM prediction, alerts) which still works great.

---

## What you'll get

After one cell, Bannin watches your notebook session and tells you:

- **How much time is left** before your session dies
- **Whether your RAM is about to crash** (predicts OOM before it happens)
- **What GPU you have** and if it got taken away
- **Whether your data is safe** (Google Drive mounted? Output under the limit?)
- **A plain-English summary** of your session health
- **A live dashboard** you can open in a browser tab

The key difference: Colab/Kaggle just crashes with no warning. Bannin tells you what's happening before it's too late.

---

## Step 1: Install Bannin

Open a new notebook (or use an existing one). Create a code cell at the very top and paste this:

```python
!gdown 'https://drive.google.com/uc?id=1UYgpMM6dMuDzzGVA-oKOmGrMghPhBt3E' -O bannin-0.1.0-py3-none-any.whl -q && pip install -q bannin-0.1.0-py3-none-any.whl
```

Run the cell. It downloads Bannin from Google Drive and installs it. Takes about 10 seconds.

**What to expect:**
- If it finishes with no red text, you're good
- You might see some grey "already satisfied" messages -- that's normal, it means the dependencies were already installed
- If you see red errors, check the Troubleshooting section at the bottom

> **How this works:** `gdown` (pre-installed on Colab) downloads a Python package file from Google Drive. `pip install` installs it along with any dependencies it needs. One line, everything handled.

---

## Step 2: See your session health

Create a new cell below and paste this:

```python
import bannin
import requests
import time

with bannin.watch():
    time.sleep(3)  # Bannin needs a moment to start its server

    # --- Your session at a glance ---
    p = requests.get("http://localhost:8420/platform").json()

    print("=== Your Session ===\n")
    print(f"  Platform:       {p['platform'].upper()} ({p.get('tier', 'unknown').upper()} tier)")
    print(f"  Time elapsed:   {p['session']['elapsed_human']}")
    print(f"  Time remaining: {p['session']['remaining_human']}")
    print(f"  Idle timeout:   {p['session']['idle_timeout_human']}")
    print(f"  GPU:            {'Yes - ' + p['gpu']['name'] if p['gpu']['assigned'] else 'None assigned'}")
    print(f"  RAM:            {p['ram']['used_gb']:.1f} GB / {p['ram']['total_gb']:.1f} GB ({p['ram']['percent']}%)")
    print(f"  Disk:           {p['storage']['used_gb']:.1f} GB / {p['storage']['total_gb']:.1f} GB ({p['storage']['percent']}%)")
    print(f"  Google Drive:   {'Mounted' if p['drive']['mounted'] else 'NOT mounted - data will be lost!'}")

    if p.get('warnings'):
        print(f"\n  Warnings:")
        for w in p['warnings']:
            print(f"    - {w}")
```

Run the cell. You should see something like this:

```
=== Your Session ===

  Platform:       COLAB (FREE tier)
  Time elapsed:   2m
  Time remaining: 11h 57m
  Idle timeout:   1h 30m
  GPU:            None assigned
  RAM:            1.0 GB / 12.7 GB (10.2%)
  Disk:           21.2 GB / 107.7 GB (19.7%)
  Google Drive:   NOT mounted - data will be lost!

  Warnings:
    - NO GPU: No GPU assigned. You may have been throttled or GPU is unavailable.
    - DRIVE NOT MOUNTED: Cannot save checkpoints to Google Drive. Data will be lost on disconnect.
```

**What each line means:**
- **Platform** -- Which notebook platform you're on, and your tier (Free, Pro, Pro+)
- **Time elapsed** -- How long you've been running this session
- **Time remaining** -- How much time before the platform kills your session (Colab free = 12 hours max)
- **Idle timeout** -- How long you can be inactive before disconnection (Colab free = 90 minutes)
- **GPU** -- Whether you have a GPU and what type (T4, P100, A100, etc.)
- **RAM** -- How much memory you're using. If this gets close to 100%, your notebook crashes
- **Disk** -- How much storage you're using. On Colab this is temporary (wiped on disconnect)
- **Google Drive** -- Whether Drive is mounted. If not, everything you save is lost when the session ends
- **Warnings** -- Plain-English alerts about things that need attention

> **"Address already in use" message?** That's harmless. It means Bannin is already running from a previous cell. Your results still work fine.

---

## Step 3: Monitor a training run

This is where Bannin earns its keep. While your model trains, Bannin watches RAM, tracks progress, and predicts crashes before they happen.

Create a new cell and paste this:

```python
import bannin
import requests
import time

with bannin.watch():
    time.sleep(3)

    # ===========================================
    # YOUR TRAINING CODE GOES HERE
    # (this is a demo -- replace with your real training)
    from tqdm import tqdm
    for epoch in tqdm(range(10), desc="Training"):
        time.sleep(2)  # simulates training work
    # ===========================================

    # --- After training: what happened? ---

    # Was memory getting dangerous?
    oom = requests.get("http://localhost:8420/predictions/oom").json()
    ram = oom.get('ram', {})
    if ram.get('trend') == 'increasing':
        print(f"WARNING: Memory was growing during training!")
        print(f"  Estimated crash in: {ram.get('minutes_until_full', '?')} minutes")
        print(f"  Confidence: {ram.get('confidence_percent', '?')}%")
    else:
        print(f"Memory stayed stable at {ram.get('current_percent', '?')}%")

    # What did Bannin track?
    tasks = requests.get("http://localhost:8420/tasks").json()
    for t in tasks.get('completed_tasks', []):
        print(f"Completed: {t.get('name', 'Task')} -- took {t.get('elapsed_human', '?')}")

    # Plain-English summary of how the system is doing
    summary = requests.get("http://localhost:8420/summary").json()
    print(f"\n{summary['headline']}")
    print(summary['details'])
```

**What this tells you that Colab/Kaggle doesn't:**
- **Was RAM creeping up during training?** Colab just crashes with no warning. Bannin tells you "memory was growing at X% per minute, estimated crash in Y minutes"
- **How long did training actually take?** Bannin tracks it automatically
- **Is the system healthy or under strain?** A plain-English summary instead of guessing

> **Replace the demo code with your real training.** The `for epoch in tqdm(...)` part is just a placeholder. Put your actual model training code there. As long as you use `tqdm` for progress bars, Bannin will automatically detect and track the progress.

---

## Step 4: Check in anytime

While your code is running in another cell, you can run this cell at any time to get a quick status:

```python
import requests

# Quick status
m = requests.get("http://localhost:8420/metrics").json()
p = requests.get("http://localhost:8420/platform").json()
print(f"RAM: {m['memory']['percent']}% | CPU: {m['cpu']['percent']}% | Time left: {p['session']['remaining_human']}")

# Any problems?
alerts = requests.get("http://localhost:8420/alerts/active").json()
if alerts.get('active'):
    for a in alerts['active']:
        print(f"  [{a['severity'].upper()}] {a['message']}")
else:
    print("No alerts -- everything looks good")
```

This is fast -- no delay needed since Bannin is already running from Step 2.

---

## Step 5: Open the live dashboard (optional)

You can see a full visual dashboard right inside your notebook:

```python
from IPython.display import IFrame
IFrame('http://localhost:8420', width='100%', height=600)
```

This shows:
- **Live CPU, RAM, disk gauges**
- **Process table** with friendly names
- **Memory chart** over time
- **Alerts banner** (only when something is wrong)
- **OOM prediction** (will you run out of memory?)
- **Summary button** for a plain-English health report

> **Want the full experience?** Open `http://localhost:8420` in a new browser tab. The dashboard has a loading animation (Bannin's eye opening), smoother charts, and more room to see everything.

---

## What Bannin watches for you

### On Google Colab

| What Bannin tracks | Why it matters |
|---|---|
| Session countdown | Colab kills your session after 12h (free) or 24h (Pro). Bannin counts down so you know when to save |
| Idle timeout | Walk away for 90 minutes and Colab disconnects. Bannin tracks idle time |
| GPU assignment | Colab can give you a T4, A100, or nothing. It can take your GPU away mid-session without telling you |
| VRAM usage | If GPU memory fills up, your code crashes instantly. No warning from Colab |
| RAM usage | If RAM exceeds the limit (~13 GB free), Colab restarts your runtime. All variables gone |
| OOM prediction | Bannin tracks memory growth and warns you BEFORE you crash -- "OOM in ~12 minutes" |
| Storage | Everything on Colab's disk is temporary. When the session ends, it's wiped |
| Google Drive status | If Drive isn't mounted, there's nowhere to save permanently. Bannin warns you |
| Tier detection | Automatically figures out Free vs Pro vs Pro+ from your RAM allocation |

### On Kaggle

| What Bannin tracks | Why it matters |
|---|---|
| Session countdown | CPU sessions: 12h max. GPU sessions: 9h max. When it hits zero, your notebook is killed |
| GPU weekly quota | Kaggle gives ~30 hours/week of GPU time. Bannin tracks how much you've used |
| Dual GPU detection | Kaggle sometimes gives 2x T4 GPUs (32 GB total). Bannin detects both |
| Output limits | 20 GB max output, 500 files max. Go over and your save fails |
| Internet access | Competition notebooks disable internet. Bannin detects this so you know why pip install fails |
| RAM and CPU | Same OOM prediction and resource tracking as Colab |

### On other platforms (Paperspace, SageMaker, Lightning AI, etc.)

| What Bannin tracks | Why it matters |
|---|---|
| CPU, RAM, disk | Full system metrics with friendly process names |
| GPU (if NVIDIA) | VRAM usage, utilization, temperature |
| OOM prediction | Memory growth trend analysis -- predicts crashes before they happen |
| Smart alerts | Warnings when RAM, CPU, or disk get high |
| Plain-English summary | "Your system is healthy" or "Memory is getting tight, consider saving your work" |

> Platform-specific features (session countdown, GPU quota, tier detection) are Colab/Kaggle only for now. More platforms coming based on feedback.

---

## How Bannin adds value during a real session

Here's a real scenario. You're training a model on Colab free tier:

1. **Hour 0** -- You start training. Bannin says: "Session started. 12 hours remaining. No GPU assigned. Drive not mounted."
2. **Hour 1** -- You check in. Bannin says: "RAM at 45%. Memory stable. 11 hours left."
3. **Hour 3** -- Bannin alerts: "RAM at 78% and growing. At this rate, OOM in ~40 minutes."
4. **Hour 4** -- You reduce batch size or clear some variables. Bannin confirms: "Memory stabilized at 72%."
5. **Hour 8** -- Bannin alerts: "4 hours remaining. Consider saving your work."
6. **Hour 11** -- Bannin warns: "1 hour remaining. Save everything now."

Without Bannin: Colab crashes at hour 3 with no warning. You lose everything. You start over.

With Bannin: You see the problem coming, fix it, and finish your training.

---

## Troubleshooting

**"No module named bannin":**
The install cell didn't complete. Run it again. If it still fails, try installing dependencies manually first:
```python
!pip install -q psutil fastapi uvicorn
!gdown 'https://drive.google.com/uc?id=1UYgpMM6dMuDzzGVA-oKOmGrMghPhBt3E' -O bannin-0.1.0-py3-none-any.whl -q && pip install -q bannin-0.1.0-py3-none-any.whl
```

**"Connection refused" error:**
Bannin's server needs a few seconds to start. Make sure you have `time.sleep(3)` after `bannin.watch()` starts, before any `requests.get()` calls.

**"Address already in use" message:**
This is harmless. It means Bannin is already running from a previous cell. Your queries still work fine.

**Kaggle: install fails completely:**
You might be in a competition notebook with internet disabled. Switch to a regular notebook to try Bannin.

**Session restarted, Bannin gone:**
When Colab/Kaggle restarts your runtime, everything in memory is wiped -- including Bannin. Just re-run the install cell (Step 1) and the start cell (Step 2). Takes about 15 seconds.

**Results look wrong or show errors:**
Make sure you're running the cells in order. Step 1 (install) must complete before Step 2 (start). Step 2 must be running before Step 3 or 4.

---

## What this doesn't do (yet)

- **Phone alerts** -- Bannin can detect problems but can't ping your phone yet (coming soon)
- **Auto-checkpoint** -- Bannin warns you before a crash but can't auto-save your model to Drive yet (planned)
- **Session extending** -- Bannin does NOT try to keep your session alive. That violates Google's terms and risks your account. Instead, it warns you so you can save in time

---

## Feedback

After trying it, I'd love to know:

- Did it install and run without issues?
- Is the session info useful? What would you check most?
- What would make you install this in every notebook?
- What's confusing or missing?

Be honest -- "I don't see why I'd use this" is more helpful than "looks cool!"
