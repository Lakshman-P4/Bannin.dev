# Try Bannin on Google Colab / Kaggle

Bannin monitors your notebook session while you work. It tells you how much time you have left, whether your RAM is about to crash, if your GPU got reassigned, and whether Google Drive is mounted (so you don't lose everything when the session ends).

**One cell to install. No cloning, no accounts, no API keys.**

---

## Cell 1: Install Bannin

Paste this into a new code cell at the top of your notebook and run it:

```python
!gdown 'https://drive.google.com/uc?id=1UYgpMM6dMuDzzGVA-oKOmGrMghPhBt3E' -O bannin-0.1.0-py3-none-any.whl -q && pip install -q bannin-0.1.0-py3-none-any.whl
```

Takes about 10 seconds. If it finishes without red errors, you're good.

---

## Cell 2: Start Bannin and see your session

```python
import bannin
import requests
import time

with bannin.watch():
    time.sleep(3)  # Bannin needs a moment to start up

    # --- Your Colab/Kaggle session at a glance ---
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

You should see something like:

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

> **Note:** You might see an "address already in use" message if you run this cell twice. That's harmless -- it means Bannin is already running from the first time. The results still work.

---

## Cell 3: Monitor a training run

This is where Bannin earns its keep. While your training runs, Bannin watches RAM, tracks progress, and predicts crashes.

```python
import bannin
import requests
import time

with bannin.watch():
    time.sleep(3)

    # === Your training code goes here ===
    # (this is a demo -- replace with your real training)
    from tqdm import tqdm
    for epoch in tqdm(range(10), desc="Training"):
        time.sleep(2)

    # === After training: what happened? ===

    # Did memory get tight?
    oom = requests.get("http://localhost:8420/predictions/oom").json()
    ram = oom.get('ram', {})
    if ram.get('trend') == 'increasing':
        print(f"Memory was growing. Estimated crash in {ram.get('minutes_until_full', '?')} minutes")
        print(f"Confidence: {ram.get('confidence_percent', '?')}%")
    else:
        print(f"Memory stayed stable at {ram.get('current_percent', '?')}%")

    # What did Bannin track?
    tasks = requests.get("http://localhost:8420/tasks").json()
    for t in tasks.get('completed_tasks', []):
        print(f"Completed: {t.get('name', 'Task')} - took {t.get('elapsed_human', '?')}")

    # Plain-English summary
    summary = requests.get("http://localhost:8420/summary").json()
    print(f"\n{summary['headline']}")
    print(summary['details'])
```

**What this tells you that Colab doesn't:**
- Was RAM creeping up during training? (Colab just crashes with no warning)
- How long did the training actually take?
- Is the system healthy or under strain?

---

## Cell 4: Check in anytime (run this whenever you want)

While your code is running in another cell, you can run this to check in:

```python
import requests

# Quick status
m = requests.get("http://localhost:8420/metrics").json()
p = requests.get("http://localhost:8420/platform").json()
print(f"RAM: {m['memory']['percent']}% | CPU: {m['cpu']['percent']}% | Time left: {p['session']['remaining_human']}")

# Any problems?
alerts = requests.get("http://localhost:8420/alerts/active").json()
if alerts.get('active_alerts'):
    for a in alerts['active_alerts']:
        print(f"  [{a['severity'].upper()}] {a['message']}")
else:
    print("No alerts - everything looks good")
```

This is fast -- no delay needed since Bannin is already running.

---

## What Bannin watches for you

### On Colab

| What | Why it matters |
|---|---|
| Session countdown | Colab kills your session after 12h (free) or 24h (Pro). Bannin counts down so you know when to save. |
| Idle timeout | Walk away for 90 minutes and Colab disconnects. Bannin tracks idle time. |
| GPU assignment | Colab can give you a T4, A100, or nothing. It can also take your GPU away mid-session without telling you. |
| VRAM usage | If GPU memory fills up, your code crashes instantly. No warning from Colab. |
| RAM usage | If RAM exceeds the limit (~13 GB free tier), Colab restarts your runtime. All variables, all state -- gone. |
| Storage | Everything on disk is temporary. When the session ends, it's wiped. |
| Google Drive | If Drive isn't mounted, there's nowhere to save permanently. Bannin warns you. |
| Tier detection | Automatically figures out Free vs Pro vs Pro+ from your RAM allocation. |

### On Kaggle

| What | Why it matters |
|---|---|
| Session countdown | CPU: 12h, GPU: 9h. When it hits zero, the notebook is killed. |
| GPU weekly quota | 30 hours/week. Once you use it, no more GPU until it rolls over. |
| Dual GPU detection | Kaggle sometimes gives 2x T4 GPUs (32 GB total). Bannin detects both. |
| Output limits | 20 GB max, 500 files max. Go over and your save fails. |
| Internet access | Competition notebooks disable internet. Bannin detects this so you know why pip install fails. |

---

## Optional: See the live dashboard

Colab can show the Bannin dashboard inline:

```python
from IPython.display import IFrame
IFrame('http://localhost:8420', width='100%', height=600)
```

Or just open `http://localhost:8420` in a new browser tab for the full experience (loading eye animation, live charts, alerts banner, process table).

---

## Troubleshooting

**"No module named bannin":**
The install cell didn't complete. Run it again. If it still fails:
```python
!pip install -q psutil fastapi uvicorn
!gdown 'https://drive.google.com/uc?id=1UYgpMM6dMuDzzGVA-oKOmGrMghPhBt3E' -O bannin-0.1.0-py3-none-any.whl -q && pip install -q bannin-0.1.0-py3-none-any.whl
```

**"Connection refused" error:**
Bannin's server needs a few seconds to start. Make sure you have `time.sleep(3)` after `bannin.watch()` starts, before any `requests.get()` calls.

**"Address already in use" message:**
This is harmless. It means Bannin is already running from a previous cell. Your queries will still work fine.

**Kaggle: install fails completely:**
You might be in a competition notebook with internet disabled. Switch to a regular notebook to try Bannin.

**Session restarted, Bannin gone:**
When Colab restarts your runtime, everything in memory is wiped -- including Bannin. Just re-run Cell 1 (install) and Cell 2 (start) again. Takes ~15 seconds.

---

## What this doesn't do (yet)

- **Phone alerts** -- Bannin can detect problems but can't ping your phone yet (coming soon)
- **Auto-checkpoint** -- Bannin warns you before a crash but can't auto-save your model yet (planned)
- **Session extending** -- Bannin does NOT try to keep your session alive. That violates Google's terms and risks your account. Instead, it warns you so you can save in time.

---

## Feedback

After trying it, I'd love to know:

- Did it install and run without issues?
- Is the session info useful? What would you check most?
- What would make you install this in every notebook?
- What's confusing or missing?

Be honest -- "I don't see why I'd use this" is more helpful than "looks cool!"
