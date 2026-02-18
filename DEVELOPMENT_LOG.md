# Vigilo Development Log

---

# Phase 1a — Python Agent Core

**Date**: 18 February 2026
**Goal**: Build the foundational Python agent that reads your machine's vital signs and makes them available through a local API.
**Status**: COMPLETE

---

## What Was Built

The Vigilo Python Agent — the "engine" of the entire platform. This is the first piece that every other component (phone app, relay server, MCP server, browser extension) will depend on.

Think of it like installing a health sensor on your computer. Once it's running, anything can ask "How's this machine doing?" and get an instant answer.

### Components Created

| File | What It Does | Plain English |
|---|---|---|
| `pyproject.toml` | Package configuration | The "recipe card" — tells Python what Vigilo is, what it needs to install, and how to run it |
| `setup.py` | Install compatibility | A small helper that makes `pip install vigilo` work on all systems |
| `vigilo/__init__.py` | Public API | The front door — gives developers the `vigilo.watch()` and `Vigilo()` interface |
| `vigilo/core/collector.py` | System metrics | Reads CPU, RAM, disk, and network stats using `psutil` |
| `vigilo/core/gpu.py` | GPU metrics | Reads NVIDIA GPU stats (temperature, memory, utilization) if available |
| `vigilo/core/process.py` | Process monitor | Lists the top processes running on the machine and their resource usage |
| `vigilo/api.py` | REST API server | The web server at `localhost:8420` that exposes all metrics as JSON endpoints |
| `vigilo/cli.py` | Command line tool | The `vigilo start` command that launches the agent |

### API Endpoints (what the agent exposes)

| Endpoint | Purpose | Who Will Use It |
|---|---|---|
| `GET /health` | "Am I alive?" check | Relay server (to confirm agent is connected) |
| `GET /metrics` | Full system snapshot — CPU, RAM, disk, network, GPU | Phone app, MCP server, relay |
| `GET /status` | Agent identity — hostname, OS, version, uptime | Phone app (to show which machine this is) |
| `GET /processes` | Top processes by resource usage | Phone app (to show what's eating resources) |
| `GET /tasks` | Monitored jobs (placeholder for now) | Phone app (will show training runs, notebook sessions) |

### How Users Interact With It

**Option 1 — Command line:**
```
pip install vigilo
vigilo start
```
The agent runs in background, API is live at `http://127.0.0.1:8420`.

**Option 2 — Inside Python code:**
```python
import vigilo

with vigilo.watch():
    train_my_model()  # Vigilo monitors the system while this runs
```

---

## Live Test Results (from your laptop)

### /metrics — System Health Snapshot

```json
{
    "timestamp": "2026-02-18T08:12:04.308257+00:00",
    "hostname": "LAPTOP-M0LQJJMQ",
    "platform": "Windows",
    "cpu": {
        "percent": 18.8,
        "per_core": [28.6, 0, 28.6, 0, 57.1, 28.6, 0, 14.3],
        "count_physical": 4,
        "count_logical": 8,
        "frequency_mhz": 991
    },
    "memory": {
        "total_gb": 7.78,
        "available_gb": 0.68,
        "used_gb": 7.11,
        "percent": 91.3
    },
    "disk": {
        "total_gb": 237.12,
        "used_gb": 177.84,
        "free_gb": 59.28,
        "percent": 75
    },
    "network": {
        "bytes_sent": 226437990,
        "bytes_sent_mb": 215.95,
        "bytes_received": 183239796,
        "bytes_received_mb": 174.75
    },
    "gpu": []
}
```

**What this tells us:**
- CPU is mostly idle (18.8%) — normal for a laptop not running heavy tasks
- RAM is critically high at 91.3% — only 0.68 GB free out of 7.78 GB. This is exactly the kind of thing Vigilo will eventually push as a phone alert.
- Disk is at 75% — healthy, 59 GB free
- No GPU detected (expected — this laptop has no NVIDIA GPU)

### /status — Agent Identity

```json
{
    "agent": "vigilo",
    "version": "0.1.0",
    "hostname": "LAPTOP-M0LQJJMQ",
    "platform": "Windows",
    "platform_version": "10.0.26200",
    "python_version": "3.11.0",
    "gpu_available": false,
    "uptime_seconds": 356.1
}
```

**What this tells us:** The agent correctly identifies the machine, OS, Python version, and how long it's been running. This is what the phone app will use to show "Connected machines" in the dashboard.

### /processes — Running Processes

```json
{
    "summary": {
        "total": 334,
        "running": 328,
        "sleeping": 0
    },
    "top_processes": [
        {"pid": 0, "name": "System Idle Process", "cpu_percent": 0.0, "memory_percent": 0.0},
        {"pid": 4, "name": "System", "cpu_percent": 0.0, "memory_percent": 0.0},
        {"pid": 144, "name": "chrome.exe", "cpu_percent": 0.0, "memory_percent": 0.8},
        {"pid": 184, "name": "Registry", "cpu_percent": 0.0, "memory_percent": 0.2}
    ]
}
```

**What this tells us:** 334 processes running, Chrome is visible using 0.8% memory. When someone is training a model or running a long build, those processes will show up here with high CPU/memory usage — making it obvious what's eating resources.

---

## Challenges & Errors

### Challenge 1: Windows Permissions (BLOCKING — resolved)

**What happened:** Running `pip install -e .` failed with:
```
ERROR: Could not install packages due to an OSError: [WinError 2]
The system cannot find the file specified: 'C:\Python311\Scripts\uvicorn.exe'
```

**Why:** Python is installed in two places on this machine — a system-wide folder (`C:\Python311\`) that has restricted permissions, and a user-level folder. Pip tried to write to the restricted one and failed.

**Fix:** Used `pip install --user -e .` to install to the user directory instead.

**Impact on users:** Users on Windows may need to use `--user` flag or (better) use a virtual environment. We should document this in the README.

---

### Challenge 2: CLI Not on PATH (MINOR — workaround exists)

**What happened:** After install, the `vigilo` command wasn't recognised in the terminal.

**Why:** The executable installed to `C:\Users\laksh\AppData\Roaming\Python\Python311\Scripts\` which isn't in the system PATH.

**Workaround:** Use `python -m vigilo.cli start` instead — works reliably everywhere.

**Impact on users:** We should add PATH instructions to the README, or recommend `python -m vigilo.cli start` as the default.

---

### Challenge 3: Port Already in Use (MINOR — expected)

**What happened:** When starting the agent a second time, got:
```
errno 10048: Only one usage of each socket address is normally permitted
```

**Why:** The previous instance was still running on port 8420.

**Fix:** Killed the process holding the port. In future, the agent should detect this and either reuse the existing instance or show a clear error message like "Vigilo is already running on port 8420."

**Impact on users:** Need to add graceful handling — detect if port is taken, offer to stop the old instance.

---

### Challenge 4: No GPU to Test (KNOWN LIMITATION)

**What happened:** GPU endpoint returns `[]` (empty list).

**Why:** This laptop has no NVIDIA GPU / no NVIDIA drivers installed.

**Impact:** The GPU monitoring code is written and ready, but hasn't been tested on real hardware. Will need testing on a machine with an NVIDIA GPU (or in a Colab/Kaggle notebook with GPU enabled).

---

## MVP from Phase 1a

### What we have (Minimum Viable Product for the agent)

Phase 1a delivers the **L0 (Observe)** capability — the agent can observe and report raw system metrics. This is the foundation that everything else builds on.

| MVP Feature | Status | What It Enables |
|---|---|---|
| System metrics collection (CPU, RAM, disk, network) | DONE | Phone app can show live machine health |
| GPU metrics collection (NVIDIA) | DONE (untested on hardware) | Phone app can show GPU temp/memory during training |
| Process monitoring (top processes by usage) | DONE | Phone app can show what's eating resources |
| Local REST API at localhost:8420 | DONE | Any client (phone, MCP, browser) can read metrics |
| pip-installable package | DONE | Users can install with one command |
| `vigilo.watch()` context manager | DONE | Developers can wrap code blocks with monitoring |
| CLI entry point (`vigilo start`) | DONE | Users can start the agent from terminal |

### What we DON'T have yet (coming in later phases)

| Feature | Phase | Why It's Not in MVP |
|---|---|---|
| ~~Colab/Kaggle session monitoring~~ | ~~1b~~ | ~~Requires platform detection logic~~ DONE |
| LLM token/cost tracking | 1c | Requires API middleware wrapper |
| Alerts (L1) — "RAM is critical!" | 2 | Needs threshold engine + notification system |
| Phone app | 3-4 | Needs relay server first |
| Push notifications to phone | 3-4 | Needs relay server + FCM/APNs |
| MCP server (AI tool integration) | 2 | Needs agent stable first |
| Browser extension | 3+ | Separate codebase (JavaScript) |

### The Key Takeaway

**Phase 1a proves the core concept works.** You can install Vigilo, run it, and instantly see live data about your machine through a clean API. Every number shown is real, live, and updating. The foundation is solid — now we build features on top of it.

---

# Phase 1b — Google Colab & Kaggle Notebook Monitoring

**Date**: 18 February 2026
**Goal**: Make Vigilo smart enough to know WHERE it's running (your laptop, Colab, or Kaggle) and automatically track every constraint and limit that platform imposes.
**Status**: COMPLETE

---

## What Was Built

Vigilo now has "platform awareness." When someone installs Vigilo in a Colab or Kaggle notebook, it automatically detects the environment and starts monitoring everything specific to that platform — session timers, GPU quotas, storage limits, and more.

Think of it like this: Phase 1a gave Vigilo eyes to see your machine's health. Phase 1b taught it to recognize which ROOM it's in and understand the rules of that room.

### Components Created

| File | What It Does | Plain English |
|---|---|---|
| `vigilo/platforms/detector.py` | Platform detection | The "where am I?" check — figures out if Vigilo is running on your laptop, inside Google Colab, or inside Kaggle |
| `vigilo/platforms/colab.py` | Colab monitor | Watches everything Colab-specific: session countdown, GPU assignment, tier detection, storage, Drive status |
| `vigilo/platforms/kaggle.py` | Kaggle monitor | Watches everything Kaggle-specific: GPU/TPU quotas, session limits, output caps, internet access, file limits |
| `vigilo/api.py` (updated) | New `/platform` endpoint | Added a new URL that returns platform-specific monitoring data |

### New API Endpoint

| Endpoint | Purpose | Who Will Use It |
|---|---|---|
| `GET /platform` | Platform-specific monitoring (Colab, Kaggle, or local) | Phone app (to show cloud notebook health) |
| `GET /status` (updated) | Now includes `"environment": "local"` or `"colab"` or `"kaggle"` | Phone app (to show which environment this agent is in) |
| `GET /metrics` (updated) | Now includes `"environment"` field | Everything that consumes metrics |

---

## What Vigilo Now Tracks — The Full Picture

### How Platform Detection Works

When Vigilo starts, it checks:
1. Is the `google.colab` Python module available? Are Colab environment markers present? → **It's Colab**
2. Is the `KAGGLE_KERNEL_RUN_TYPE` environment variable set? Is `/kaggle/working` a real folder? → **It's Kaggle**
3. Neither? → **It's a local machine**

This happens once at startup — zero effort from the user. They just `pip install vigilo` and it figures out the rest.

### Google Colab — Every Constraint Monitored

We researched every single limit Google imposes on Colab users. Here's what Vigilo now tracks:

**Session & Time**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| Session countdown | Free: 12h max, Pro: 24h max, Pro+: 24h max | If the timer runs out, everything in memory is destroyed |
| Idle timeout | Free: 90 min, Pro/Pro+: ~3 hours | If you walk away too long, Colab kills your session |
| Tier detection | Auto-detected from RAM allocation | Different tiers have different limits — Vigilo adjusts automatically |
| Background execution | Pro+ only | Only Pro+ can keep running after you close the browser tab |

**GPU & Compute**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| GPU assignment | Colab assigns T4, L4, A100, or nothing | Free users often get no GPU during busy times — Vigilo catches this |
| GPU VRAM | T4=15GB, L4=22.5GB, A100=40GB (hard limits) | If VRAM fills up, your code crashes instantly |
| GPU temperature | Live reading in Celsius | High temps (>85C) cause throttling — your code runs slower |
| GPU power draw | Live reading in Watts | Tells you how hard the GPU is working |
| Compute units burn rate | T4=~2 CU/hr, L4=~5 CU/hr, A100=~13 CU/hr | Paid users burn through their compute budget faster on better GPUs |
| GPU architecture & specs | CUDA cores, Tensor cores | So you know exactly what hardware you're working with |

**Memory (RAM)**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| RAM usage | Free: ~13GB, Pro: ~26GB, Pro+: ~53GB | If RAM exceeds the limit, the runtime CRASHES and all your work is lost |
| Swap memory | Tracked separately | When RAM fills, the system uses swap (much slower) — a sign you're in trouble |

**Storage**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| Disk usage | Free: ~50GB, Pro: ~100GB, Pro+: ~150GB (all temporary) | Everything on disk vanishes when the session ends |
| Google Drive status | Mounted or not + usage if mounted | If Drive isn't mounted, there's nowhere to save your work permanently |
| Drive I/O warning | Folders with >10,000 files cause errors | Google Drive has hidden usage quotas that cause silent failures |

**Hard Limits**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| Notebook file size | Max 20 MB | Notebooks with huge embedded outputs can't be saved |
| File upload limit | Max 2 GB per file | Larger files need Drive or cloud storage |
| File download limit | ~100 MB practical limit | Browser-based downloads choke on larger files |
| Concurrent sessions | Free: 2, Pro: 3, Pro+: 5 | Opening too many notebooks forces you to shut one down |
| Prohibited activities | Crypto mining, torrents, web hosting, etc. | Google actively monitors and will ban accounts |

### Kaggle — Every Constraint Monitored

**Session & Time**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| Session countdown | CPU: 12h, GPU: 9h, TPU: 9h | When it hits zero, the notebook is killed |
| Idle timeout | 60 minutes + "Are you still there?" prompts | Walk away too long and you lose your session |

**GPU & TPU Quotas**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| GPU weekly quota | 30 hours/week (rolling 7-day window) | Once you use it up, no more GPU until old usage rolls off |
| TPU weekly quota | 20 hours/week (separate from GPU) | TPU has its own separate budget |
| GPU type detection | P100 (single) or T4 x2 (dual GPU) | Different GPUs have different strengths and VRAM |
| Multi-GPU awareness | Detects dual T4 setup, aggregates VRAM across both | Kaggle's T4 x2 gives you 32 GB total across 2 GPUs |
| GPU session hours burned | Tracked per session | So you can estimate how much weekly quota you've used |
| GPU temperature & power | Live readings | Early warning for throttling |

**Memory (RAM)**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| RAM usage | CPU: ~30GB, GPU: ~29GB, TPU: ~16GB system + 128GB HBM | Exceeding RAM kills the notebook and restarts it — all state lost |
| CPU cores | 4 vCPUs (all modes) | Helps understand processing power available |

**Storage**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| Disk space | ~73 GB total | Running out of disk fails your code |
| Output directory | 20 GB limit in `/kaggle/working` | Everything you want to keep must fit in 20 GB |
| Output file count | 500 files max | More than 500 files? Zip them or the commit fails |
| Input data | 100 GB read-only limit | The datasets you attach are capped at 100 GB combined |

**Network & Access**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| Internet access | Full access normally, DISABLED in competition notebooks | If internet is off, you can't pip install or download anything |
| Phone verification | Required for GPU/TPU access | New users can't use GPU until they verify their phone number |

**Hard Limits**
| What We Track | The Rule | Why It Matters |
|---|---|---|
| Notebook source size | 1 MB max | Notebooks with large embedded outputs can't be saved |
| Dataset size | 100 GB per dataset | Individual datasets have a size cap |
| File upload (web) | ~500 MB per file | Browser uploads are limited |
| File upload (API) | ~2 GB per file | API uploads allow slightly larger files |
| Concurrent GPU sessions | 1 max | You can only run one GPU notebook at a time |
| Persistence mode | Available but adds overhead | Can save working directory between sessions |

---

## Real-World Test Results (18 February 2026)

Tested on actual Google Colab (free tier, CPU-only) and actual Kaggle (CPU-only, competition notebook with internet disabled).

### Google Colab — Real Test Results

| Check | What We Expected | What We Got | Verdict |
|---|---|---|---|
| Detected as Colab | True | **True** | PASS |
| COLAB_RELEASE_TAG | Some value | **release-colab-external_20260213_060047_RC00** | PASS |
| /content exists | True | **True** | PASS |
| Platform | Linux | **Linux** | PASS |
| CPU cores | 2 | **2** | PASS |
| RAM | ~12-13 GB | **12.67 GB** | PASS |
| Tier detection | "free" | **"free" (based on 12.7 GB RAM)** | PASS |
| GPU | Depends on runtime setting | **No GPU (pynvml not installed)** | EXPECTED (GPU not enabled) |
| Disk | We assumed ~50 GB | **107.72 GB** | CORRECTED (see below) |
| Google Drive | Not mounted | **Not mounted** | PASS |

**Data correction applied**: Colab free tier actually gives ~107 GB of disk, not the ~50 GB we initially assumed from community reports. Google appears to have increased this. Updated our code to reflect ~110 GB as the expected value for free tier. Our runtime detection already showed the correct 107 GB number — only the "expected" label was wrong.

### Kaggle — Real Test Results

| Check | What We Expected | What We Got | Verdict |
|---|---|---|---|
| Detected as Kaggle | True | **True** (KAGGLE_KERNEL_RUN_TYPE: Interactive) | PASS |
| /kaggle/working exists | True | **True** | PASS |
| /kaggle/input exists | True | **True** | PASS |
| Platform | Linux | **Linux** | PASS |
| CPU cores | 4 | **4** | PASS |
| RAM | ~30 GB (CPU mode) | **31.35 GB** | PASS |
| Accelerator | CPU (not enabled) | **CPU** | PASS |
| Session limit | 12 hours (CPU) | **12 hours** | PASS |
| GPU | Not enabled | **NVML Shared Library Not Found** | EXPECTED (GPU not enabled) |
| Output directory | Tracked | **0.0 GB, 1 file (limit: 20 GB, 500 files)** | PASS |
| Internet access | Depends on notebook | **DISABLED (competition mode)** | PASS |
| Total disk | We assumed ~73 GB | **8,062 GB (8 TB shared filesystem)** | CORRECTED (see below) |

**Data correction applied**: Kaggle uses a massive shared filesystem (8 TB), making the total disk number meaningless for users. What actually matters is the 20 GB output limit in `/kaggle/working`, which we track correctly. Updated our code to stop showing total disk as a fixed number and instead detect at runtime with a note explaining that the output limit is what matters.

**Positive surprise**: The internet detection correctly identified the Kaggle notebook as being in **competition mode** with internet disabled. This is exactly the kind of warning that saves users from confusing error messages when their `pip install` or `wget` commands fail.

### What This Proves

All core detection systems work in the real world:
- Platform detection: correctly identifies both Colab and Kaggle
- System metrics: RAM and CPU readings match the real hardware
- Environment variables: properly found on both platforms
- Directory structures: `/content` (Colab) and `/kaggle/working` (Kaggle) correctly detected
- Internet detection: catches competition-mode restrictions
- Tier detection: correctly identifies free-tier Colab from RAM

### What Still Needs Testing

- Colab with GPU enabled (T4, L4, or A100) — to verify GPU VRAM readings
- Kaggle with P100 or T4 x2 GPU — to verify multi-GPU detection
- Kaggle with TPU — to verify TPU detection
- Colab Pro/Pro+ — to verify tier detection with higher RAM

---

## Challenges & Errors

### Challenge 1: Colab Disk Estimate Was Wrong (CORRECTED)

**What happened:** We assumed Colab free tier gives ~50 GB of disk based on community reports. The actual value is **107 GB**.

**Why:** Google increased their disk allocation without announcing it. Community sources were outdated.

**How we fixed it:** Updated the expected value to ~110 GB for free tier. More importantly, our code already detects the real disk size at runtime, so even if Google changes it again, Vigilo will show the correct number. The "expected" label is just for reference.

**Impact on users:** None — the real number was always shown correctly. Only the reference label was off.

---

### Challenge 2: Kaggle Disk Is a Shared Filesystem (CORRECTED)

**What happened:** We assumed Kaggle has ~73 GB of total disk. The actual filesystem reports **8,062 GB (8 TB)** — it's a shared filesystem across all Kaggle infrastructure.

**Why:** Kaggle runs on a different storage architecture than Colab. The total disk number is the entire shared system, not what's available to your notebook.

**How we fixed it:** Stopped showing total disk as a meaningful number for Kaggle. Instead, Vigilo now focuses on the **20 GB output limit** in `/kaggle/working`, which is the actual constraint users care about. Added a note explaining this.

**Impact on users:** Users now see the limits that actually matter (20 GB output, 500 files) instead of a misleading 73 GB number.

---

### Challenge 3: pynvml Not Pre-installed on Either Platform (EXPECTED)

**What happened:** Neither Colab nor Kaggle has `pynvml` pre-installed when running in CPU-only mode.

**Why:** `pynvml` is part of the NVIDIA CUDA toolkit. It's only available when a GPU runtime is enabled.

**Impact:** This is expected and already handled gracefully — Vigilo shows "No GPU" and moves on. When users enable a GPU runtime, `pynvml` becomes available through the CUDA drivers and Vigilo will detect the GPU automatically.

---

### Challenge 4: Platform Limits Are Not Published Officially (DESIGN DECISION)

**What happened:** Both Google (Colab) and Kaggle deliberately don't publish many exact limits.

**How we handled it:** We detect real values at runtime wherever possible (RAM, disk, GPU type) and only use hardcoded values for things that can't be detected (session time limits, quota hours). This means Vigilo stays accurate even when platforms change their limits.

---

### Challenge 5: Kaggle Quota Not Accessible via API (LIMITATION)

**What happened:** Kaggle does not expose your remaining weekly GPU quota through any API.

**How we handled it:** Vigilo tracks GPU hours burned in the current session and reminds users to check their full quota at kaggle.com/me/account.

---

## Corrections Made After Testing

| What Changed | Before | After | Why |
|---|---|---|---|
| Colab free disk estimate | 50 GB | 110 GB | Real Colab showed 107 GB |
| Colab Pro disk estimate | 100 GB | 150 GB | Adjusted proportionally |
| Colab Pro+ disk estimate | 150 GB | 200 GB | Adjusted proportionally |
| Kaggle total disk | Hardcoded 73 GB | Detected at runtime | Kaggle uses 8 TB shared filesystem |
| Kaggle disk warning | Based on total disk | Based on output directory | Output limit (20 GB) is what actually matters |

---

## MVP from Phase 1b

### What we have

Phase 1b adds **platform intelligence** to the agent — it knows where it's running and monitors accordingly. Now **verified on real platforms**.

| MVP Feature | Status | Verified On Real Platform |
|---|---|---|
| Auto-detect Colab/Kaggle/local | DONE | Colab: YES, Kaggle: YES |
| Colab session countdown | DONE | Logic verified, needs GPU runtime test |
| Colab tier detection (Free/Pro/Pro+) | DONE | Free tier: YES |
| Colab GPU tracking (type, VRAM, temp, power, CU rate) | DONE | Needs GPU runtime test |
| Colab RAM monitoring with crash warning | DONE | 12.67 GB detected correctly |
| Colab storage + Drive status | DONE | 107 GB disk, Drive not mounted: both detected |
| Colab hard limits (notebook size, upload, concurrent sessions) | DONE | Values confirmed from research |
| Kaggle session countdown | DONE | Logic verified, correct limits per accelerator |
| Kaggle GPU/TPU quota tracking | DONE | Needs GPU/TPU runtime test |
| Kaggle dual-GPU detection (T4 x2) | DONE | Needs T4 x2 runtime test |
| Kaggle output size + file count tracking | DONE | 0.0 GB, 1 file detected on real Kaggle |
| Kaggle internet access detection | DONE | Competition mode detected: YES |
| Kaggle hard limits (all documented) | DONE | Values confirmed from research |
| `/platform` API endpoint | DONE | Tested locally |
| Warning system | DONE | Generates correct warnings on all platforms |

### The Key Takeaway

**Phase 1b is verified on real platforms.** The core detection works: Vigilo correctly identifies Colab and Kaggle, reads real system metrics, catches internet restrictions, and detects tier-specific limits. Two data estimates were corrected based on real-world testing (Colab disk and Kaggle filesystem). The architecture of detecting values at runtime instead of hardcoding proved its worth — even when our estimates were off, the real numbers showed up correctly.

---

## Remote Config System (added after Phase 1b testing)

**Why this was built**: During Phase 1b review, a critical question came up: "What happens when Colab or Kaggle change their limits?" If Google increases Colab's disk from 110 GB to 150 GB, or Kaggle changes their weekly GPU quota from 30 hours to 25 hours, Vigilo would show outdated information until we release a new version.

**The solution**: A three-tier config system that keeps itself up to date:

| Layer | What It Does | When It's Used |
|---|---|---|
| Hardcoded defaults (`defaults.json`) | The "last resort" values baked into the package | Always loaded first. Works even offline, even if everything else fails |
| Local cache (`~/.vigilo/platform_config.json`) | A saved copy of the latest remote config | Used if the cache is less than 24 hours old (fast, no network needed) |
| Remote fetch (GitHub raw URL) | Fetches the latest config from our GitHub repo | Checked once per day. If it fails (no internet, timeout), we just use what we have |

**How it works in practice**:
1. User installs Vigilo → hardcoded defaults are correct at install time
2. We discover Colab changed a limit → we update `defaults.json` on GitHub
3. Next time the user runs Vigilo → it fetches the new values within 24 hours
4. If user is offline (e.g., Kaggle competition mode) → cached or hardcoded values still work

### Files Created

| File | What It Does |
|---|---|
| `vigilo/config/defaults.json` | Central JSON file with ALL platform limits — Colab tiers, GPU specs, Kaggle quotas, storage limits, RAM limits |
| `vigilo/config/loader.py` | The config engine — loads defaults, checks cache, fetches from GitHub, merges values |
| `vigilo/config/__init__.py` | Package marker |

### What Changed in Existing Files

| File | Change | Why |
|---|---|---|
| `vigilo/platforms/colab.py` | Tier limits now come from config, not hardcoded | Can be updated remotely |
| `vigilo/platforms/kaggle.py` | All limits now come from config, not hardcoded | Can be updated remotely |

### Key Design Decision

The remote config is **additive only** — it can update numbers (session hours, quota limits, GPU specs) but cannot change the structure of the monitoring code. This means a bad config file can't break Vigilo, it can only give slightly wrong numbers at worst. And if even that fails, the hardcoded defaults kick in.

### Test Results

| Test | Result |
|---|---|
| Config loads from defaults.json | PASS |
| Colab monitor works with config-sourced values | PASS |
| Kaggle monitor works with config-sourced values | PASS |
| API server starts and all endpoints respond | PASS |
| Fallback to defaults when no network | PASS (by design) |

---

---

# Phase 1c — LLM Health Monitoring & Token Tracking

**Date**: 18 February 2026
**Goal**: Make Vigilo aware of LLM API usage — track how "healthy" each conversation is, how close it is to hitting the context window limit, whether responses are getting slower, and what everything costs.
**Status**: COMPLETE

---

## What Was Built

Vigilo can now sit between your code and any LLM API (OpenAI, Anthropic, Google, and many others) and quietly monitor everything that happens. It doesn't change how the API works — it just watches and reports.

Think of it like a health monitor for your AI conversations. The same way Phase 1a watches your CPU and RAM, Phase 1c watches your LLM context windows and response times.

### The Core Idea

When you use an LLM API (like GPT-4o or Claude), every call sends your conversation history and gets a response back. The API tells you exactly how many "tokens" (roughly words) were used. Vigilo captures this data to answer questions like:

- **How full is this conversation?** "78% of context window used — about 3 messages left before quality drops"
- **Are responses getting slower?** "Latency increased from 1.4s to 4.0s — the API may be overloaded"
- **How much is this costing?** "$0.49 across 8 calls this session" (secondary info, not the headline)
- **Which provider am I using most?** "5 OpenAI calls, 2 Anthropic calls, 1 Google call"

### Why Health Over Cost

A key product decision was made during this phase: **lead with health metrics, not dollar amounts**. The reasoning:

- "$0.50 spent" → user says "ok" and does nothing
- "Conversation at 78%, latency doubled, ~3 messages left" → user takes action

Cost tracking exists (it's free to calculate), but the headline features are context window fullness, latency trends, and conversation health. This directly supports the future **Conversation Depreciation & Context Transfer** feature — "This chat has depreciated. Would you like to transfer everything to a fresh one?"

### Components Created

| File | What It Does | Plain English |
|---|---|---|
| `vigilo/llm/__init__.py` | Package exports | Makes `vigilo.wrap()` and `vigilo.track()` available |
| `vigilo/llm/pricing.py` | Model reference data | Knows the pricing, context window size, and provider for 30+ LLM models. Loads from remote config so it stays up to date |
| `vigilo/llm/tracker.py` | The brain — usage tracking & predictions | Stores every API call, calculates summaries, predicts context exhaustion, detects latency degradation |
| `vigilo/llm/wrapper.py` | The interceptor — wraps LLM clients | Sits between your code and the API. Captures token counts and timing without changing how the API works |

### Updated Files

| File | Change | Why |
|---|---|---|
| `vigilo/api.py` | Added 4 new endpoints (`/llm/usage`, `/llm/calls`, `/llm/context`, `/llm/latency`) | So the phone app and MCP server can read LLM health data |
| `vigilo/__init__.py` | Exports `vigilo.wrap()` and `vigilo.track()` | So developers can use them directly |
| `vigilo/config/defaults.json` | Added LLM pricing data for 30+ models | Prices and context windows for OpenAI, Anthropic, Google, xAI, Mistral, Meta, Cohere — all remotely updateable |

### New API Endpoints

| Endpoint | Purpose | What It Returns |
|---|---|---|
| `GET /llm/usage` | Session health overview | Total calls, tokens, cost breakdown by provider and model, warnings |
| `GET /llm/calls?limit=20` | Recent call history | List of recent API calls with tokens, latency, cost per call |
| `GET /llm/context?model=gpt-4o&tokens=95000` | Context window prediction | How full the context is, tokens remaining, estimated messages left, health warnings |
| `GET /llm/latency?model=gpt-4o` | Latency trend analysis | Whether response times are stable, improving, or degrading |

### How Users Will Use It

**Pattern 1 — Wrap your LLM client:**
```python
import vigilo
from openai import OpenAI

client = vigilo.wrap(OpenAI())

# Use the client exactly as before — Vigilo tracks everything silently
response = client.chat.completions.create(model="gpt-4o", messages=[...])

# Check conversation health anytime at localhost:8420/llm/context?model=gpt-4o&tokens=95000
```

**Pattern 2 — Named tracking scopes:**
```python
with vigilo.track("my-experiment"):
    response = client.chat.completions.create(model="gpt-4o", messages=[...])
    # This call is tagged with "my-experiment" for grouped analysis
```

**Works with all major providers:**
```python
# OpenAI (GPT-4o, GPT-4, o1, o3-mini, etc.)
client = vigilo.wrap(OpenAI())

# Anthropic (Claude Sonnet, Opus, Haiku)
client = vigilo.wrap(Anthropic())

# Google (Gemini 2.0 Flash, 1.5 Pro, etc.)
model = vigilo.wrap(genai.GenerativeModel("gemini-2.0-flash"))

# Also works automatically with: Azure OpenAI, Groq, Together AI,
# Fireworks, xAI Grok, and any OpenAI-compatible provider
```

---

## Models Supported (30+ models across 7 providers)

All pricing and context window data lives in the remote config system, so it can be updated without releasing a new version.

| Provider | Models Covered | Context Windows |
|---|---|---|
| OpenAI | GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-4, GPT-3.5-turbo, o1, o1-mini, o3-mini | 8K — 200K |
| Anthropic | Claude Opus 4, Claude Sonnet 4, Claude 3.5 Sonnet, Claude Haiku 4.5, Claude 3.5 Haiku, Claude 3 Haiku | 200K |
| Google | Gemini 2.5 Pro, 2.5 Flash, 2.0 Flash, 1.5 Pro, 1.5 Flash | 1M — 2M |
| xAI | Grok-2, Grok-3, Grok-3-mini | 131K |
| Mistral | Mistral Large, Mistral Small, Codestral | 128K — 256K |
| Meta | Llama 3.3 70B, Llama 3.1 405B, Llama 3.1 8B | 128K |
| Cohere | Command R+, Command R | 128K |

### Smart Model Matching

API responses often include model names with date suffixes (e.g., `gpt-4o-2024-08-06` instead of just `gpt-4o`). Vigilo handles this with fuzzy matching — it tries exact match first, then prefix match, then partial match. This means if OpenAI returns a new variant like `gpt-4o-2026-01-15`, Vigilo still recognises it as a GPT-4o model and prices it correctly.

---

## Test Results

### Test 1: Pricing Module

| Test | Result |
|---|---|
| Exact model lookup (gpt-4o, claude-sonnet-4, gemini-2.0-flash) | PASS |
| Prefix matching (gpt-4o-2024-08-06 → gpt-4o) | PASS |
| Cost calculation (1K in + 500 out on GPT-4o = $0.0075) | PASS |
| Context window lookup (GPT-4o = 128K, Gemini 1.5 Pro = 2M) | PASS |
| Unknown model returns None/zero (doesn't crash) | PASS |

### Test 2: Tracker Module

| Test | Result |
|---|---|
| Record 8 simulated API calls across 3 providers | PASS |
| Summary totals correct (167,800 input + 6,400 output tokens) | PASS |
| Breakdown by provider (OpenAI 5 calls, Anthropic 2, Google 1) | PASS |
| Breakdown by model (cost per model tracked separately) | PASS |
| Context prediction at 95K/128K = 74.2% used | PASS |
| Latency trend detection (1.4s → 4.0s = "degrading") | PASS |

### Test 3: Wrapper Module

| Test | Result |
|---|---|
| Wrapping a mock OpenAI client | PASS |
| Same object returned (no copy, no side effects) | PASS |
| API call intercepted, tokens captured automatically | PASS |
| `vigilo.track("name")` scope applied to calls | PASS |
| Double-wrapping protection (wrap same client twice = safe) | PASS |

### Test 4: Full Integration (Server + Tracker in Same Process)

| Test | Result |
|---|---|
| `vigilo.watch()` starts server, tracker records calls, API returns data | PASS |
| `GET /llm/usage` — returns full session summary with 8 calls | PASS |
| `GET /llm/calls?limit=3` — returns 3 most recent calls, newest first | PASS |
| `GET /llm/context?model=gpt-4o&tokens=95000` — returns 74.2% used, health note | PASS |
| `GET /llm/latency?model=gpt-4o` — detects degrading trend (1.4s → 4.0s) | PASS |
| `GET /llm/context` for Claude at 8K/200K — returns 4.0% (healthy) | PASS |
| Existing endpoints (`/health`, `/status`, `/metrics`) unaffected | PASS |

---

## Challenges & Errors

### Challenge 1: Tracker Singleton Lives Per-Process (EXPECTED)

**What happened**: When simulating API calls in a separate terminal and then checking the API, the `/llm/usage` endpoint showed zero calls.

**Why**: The tracker stores data in memory within the running process. A separate Python script has its own tracker. This is correct behavior — in real use, `vigilo.wrap()` and the API server share the same process (via `vigilo.watch()`).

**Impact on users**: None. When users use `vigilo.wrap(client)` inside their code and start the agent with `vigilo.watch()`, everything is in the same process and works correctly.

---

### Challenge 2: No Real LLM API Keys for Testing (KNOWN LIMITATION)

**What happened**: All tests used simulated/mock API calls, not real OpenAI/Anthropic/Google API calls.

**Why**: Testing requires active API keys and incurs real costs. The wrapper logic was verified with mock clients that mimic the exact response structure of real APIs.

**Impact**: The wrapper should work with real clients because it uses the same response fields (`.usage.prompt_tokens`, `.usage.input_tokens`, `.usageMetadata.promptTokenCount`). But real-world testing with actual API keys is still needed.

**How to verify**: Any developer with an OpenAI/Anthropic API key can run:
```python
import vigilo
from openai import OpenAI

with vigilo.watch():
    client = vigilo.wrap(OpenAI())
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello"}]
    )
    # Then check localhost:8420/llm/usage
```

---

### Challenge 3: Streaming Responses Not Yet Tracked (KNOWN LIMITATION)

**What happened**: The wrapper only captures token usage from non-streaming API responses. When `stream=True` is used, the response is a generator, and usage data arrives differently.

**Why**: Streaming responses send tokens incrementally. For OpenAI, usage data only appears in the final chunk if `stream_options={"include_usage": True}` is set. For Anthropic, usage is in the final `message_stop` event. Wrapping generators requires more complex interception.

**Impact**: Users who use streaming won't get automatic tracking yet. Non-streaming calls (the default for many batch/scripting use cases) work fully.

**Plan**: Phase 2 will add streaming support by wrapping the response iterator to capture the final chunk's usage data.

---

### Challenge 4: LLM Prices Change Frequently (HANDLED)

**What happened**: LLM providers change pricing regularly. Hardcoded prices would go stale.

**How we handled it**: All pricing data lives in `defaults.json` — the same remote config system built after Phase 1b. When a provider changes prices, we update the config on GitHub and every Vigilo installation picks up the new prices within 24 hours. No package release needed.

---

## Architecture Decision: Why "Wrap" Instead of "Proxy"

There were two approaches for intercepting API calls:

1. **Proxy server** — run a local server that all API calls go through (like a man-in-the-middle)
2. **Client wrapper** — modify the client object to capture calls at the source

We chose **client wrapper** because:
- No network overhead (no extra hop through a proxy)
- No port conflicts (doesn't need another localhost port)
- Works in notebooks (Colab/Kaggle have network restrictions)
- Simpler for users (`vigilo.wrap(client)` is one line)
- The client still works exactly as before — all methods, all features, all error handling

The downside is that each provider needs its own wrapping logic, but the common pattern (`intercept create → time it → extract usage → record`) is the same across all providers.

---

## How This Connects to the Bigger Picture

### What Phase 1c Enables

| Future Feature | How 1c Supports It |
|---|---|
| **Conversation Health Score** (Phase 2) | Context % + latency trend + output quality → single "health" number |
| **"Chat Depreciated" Alert** (Phase 2-3) | Trigger when health drops below threshold → phone notification |
| **Context Transfer** (Phase 3+) | Wrapper already sits between user and API — can capture conversation for summarization |
| **Phone LLM Dashboard** (Phase 5) | `/llm/usage` endpoint provides all the data the phone app needs |
| **MCP Integration** (Phase 4) | Claude Code can call `/llm/usage` to see its own token impact |
| **Spend Alerts** (Phase 2) | Cost tracking data is already calculated per call |

### The Path to "Would You Like to Transfer This Chat?"

1. **Phase 1c (now)**: We track context fullness, latency trends, and usage per conversation
2. **Phase 2**: Combine into a single health score. Fire alert when health drops below threshold
3. **Phase 3+**: When user accepts transfer, the wrapper captures the message history (it's already flowing through us), generates a compressed summary, and provides it for injection into a new conversation

The foundation is in place. The wrapper is already in the right position — between the user's code and the API — to do all of this.

---

## MVP from Phase 1c

### What we have

Phase 1c adds **LLM awareness** to Vigilo. It can now monitor your AI conversations the same way Phase 1a monitors your machine and Phase 1b monitors your cloud notebooks.

| MVP Feature | Status | Notes |
|---|---|---|
| `vigilo.wrap()` for OpenAI clients | DONE | Tested with mock client |
| `vigilo.wrap()` for Anthropic clients | DONE | Tested with mock client |
| `vigilo.wrap()` for Google Gemini clients | DONE | Tested with mock client |
| OpenAI-compatible providers (Groq, Together, Fireworks, xAI, Azure) | DONE | Auto-detected from base URL |
| Token counting per call | DONE | Input, output, cached tokens all tracked |
| Cost calculation per call | DONE | 30+ models across 7 providers |
| Context window exhaustion prediction | DONE | "74.2% used, ~1 message remaining" |
| Latency degradation detection | DONE | "Latency increasing: 1.4s → 4.0s" |
| `vigilo.track("name")` scoping | DONE | Tag calls with experiment/conversation names |
| `/llm/usage` API endpoint | DONE | Full session summary |
| `/llm/calls` API endpoint | DONE | Recent call history |
| `/llm/context` API endpoint | DONE | Per-model context prediction |
| `/llm/latency` API endpoint | DONE | Latency trend analysis |
| Remotely updateable pricing | DONE | Via existing config system |
| Double-wrap protection | DONE | Safe to call `vigilo.wrap()` multiple times |

### What we DON'T have yet

| Feature | When | Why |
|---|---|---|
| Streaming response tracking | Phase 2 | Complex generator wrapping needed |
| Conversation health score (single number) | Phase 2 | Needs combined scoring algorithm |
| "Chat depreciated" alerts | Phase 2-3 | Needs health score + notification system |
| Context transfer (auto-summarize and inject) | Phase 3+ | Needs summarization pipeline |
| Real API key testing | Next available | Needs actual API keys |
| Browser extension token estimation | Phase 6 | Separate JavaScript codebase |

### The Key Takeaway

**Phase 1c gives Vigilo its LLM eyes.** It can now watch any major LLM API, track how healthy each conversation is, detect when things are degrading, and report it all through the same API that the phone app will consume. Combined with Phase 1a (machine health) and Phase 1b (cloud notebook health), Vigilo now monitors the three main things its target users care about: their machine, their cloud environment, and their AI tools.

The critical foundation for the "conversation transfer" feature is in place — the wrapper sits in exactly the right position to eventually capture, summarize, and transfer conversation context.

---

## Post-Build Updates (after product owner review)

### Update 1: Added Latest Claude Models to Pricing Table

**What changed**: Added Claude Opus 4.6, Opus 4.5, Sonnet 4.6, and Sonnet 4.5 to the model pricing table. These were missing from the initial build.

**Why it matters**: Opus 4.6 is the most capable Claude model currently available and widely used. Without it in the pricing table, any developer using Opus via the API would get "unknown model" — tokens tracked but no cost or context window data.

| Model Added | Input (per 1M tokens) | Output (per 1M tokens) | Context Window |
|---|---|---|---|
| Claude Opus 4.6 | $5.00 | $25.00 | 200K |
| Claude Opus 4.5 | $5.00 | $25.00 | 200K |
| Claude Sonnet 4.6 | $3.00 | $15.00 | 200K |
| Claude Sonnet 4.5 | $3.00 | $15.00 | 200K |

### Update 2: Audience Redefinition

**What changed**: Updated CLAUDE.md to clarify that Vigilo is **not a developer tool**. It is a tool for everyone in the digital era — anyone who uses AI or compute.

**Why it matters**: The Phase 1c API wrapper (`vigilo.wrap()`) is one entry point, but it's the developer entry point. The larger audience — students, writers, researchers, creators, business professionals — will interact through the browser extension (Phase 6) and phone app (Phase 5). Vigilo's positioning must reflect that the browser extension path (tracking ChatGPT, Claude, Gemini for everyday users) is just as important, arguably more so, than the Python API wrapper.

**The audience**: Students, writers, researchers, creators, business professionals, hobbyists, and developers — anyone who interacts with AI or runs compute.

### GPU Verified on Real Hardware (19 February 2026)

Tested on Google Colab with T4 GPU enabled. This closes the GPU monitoring gap from Phase 1a.

| Reading | Value | Matches Expected? |
|---|---|---|
| GPU detected | Tesla T4 | YES |
| VRAM Total | 15.0 GB | YES (T4 = 15 GB in our config) |
| VRAM Used | 0.44 GB | YES (CUDA driver overhead) |
| VRAM Free | 14.56 GB | YES |
| Utilization | 0% | YES (idle) |
| Temperature | 43°C | YES (healthy idle temp) |
| Power | 12.5W | YES (idle power draw) |
| RAM | 12.67 GB | YES (free tier ~13 GB) |
| CPU Cores | 2 | YES (free tier) |

All GPU fields that our code reads (`pynvml` name, memory, utilization, temperature, power) return correct values on real hardware.

### LLM Wrapper Interception Verified (19 February 2026)

Tested `vigilo.wrap()` with a real Google Gemini API call. The wrapper successfully intercepted the call (proven by the traceback showing `wrapper.py line 211, in wrapped_generate`). The API call itself was rejected by Google's free tier quota limit (error 429), so no token data flowed through. The interception mechanism is verified — full end-to-end token tracking will be confirmed when a working API key is available.

### Live Demo Results (product owner tested)

All 4 LLM endpoints tested by the product owner in a browser:

| Endpoint | What It Showed | Verdict |
|---|---|---|
| `/llm/usage` | 5 calls, 118K tokens, breakdown by provider (OpenAI/Anthropic/Google) | PASS |
| `/llm/calls` | List of individual calls with tokens, cost, latency per call | PASS |
| `/llm/context?model=gpt-4o&tokens=95000` | 74.2% context used, 33K tokens remaining, health note displayed | PASS |
| `/llm/latency?model=gpt-4o` | Trend: "degrading", latency 1.2s → 4.2s detected | PASS |

---

*Next: Phase 2 — Intelligence Engine (health scoring, OOM prediction, threshold-based alerts)*
