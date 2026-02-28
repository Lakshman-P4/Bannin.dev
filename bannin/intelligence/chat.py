"""Bannin chatbot engine -- rule-based, data-driven system health assistant.

Detects user intent from natural language, pulls real metrics from Bannin
collectors, and returns actionable responses. No external LLM dependency.
"""

from __future__ import annotations

import os
import platform
import re
import threading
import time
from pathlib import Path
from typing import Callable

from bannin.core.collector import get_cpu_metrics, get_memory_metrics, get_disk_metrics
from bannin.core.process import get_grouped_processes, get_resource_breakdown
from bannin.log import logger


# ---------------------------------------------------------------------------
# Intent detection -- ordered by priority (more specific first)
# ---------------------------------------------------------------------------

_INTENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("unsupported", re.compile(
        r"battery|charge|charg|wifi|wi-fi|bluetooth|screen bright|volume|"
        r"weather|time|date|alarm|timer|reminder|calendar|email|message|"
        r"play music|open app|launch|install .+|download .+|"
        r"search (for|google|the web)|browse|internet speed|ping|"
        r"screenshot|camera|photo|record|password|login",
        re.IGNORECASE,
    )),
    ("history", re.compile(
        r"what happened|while i was (away|gone|out)|recent events|event log|history|"
        r"what did i miss|anything happen|any alerts|past alerts|^alerts?[\s!?.]*$",
        re.IGNORECASE,
    )),
    ("ollama", re.compile(
        r"ollama|local (model|llm)|what model.*(running|loaded)|llama|mistral.*local",
        re.IGNORECASE,
    )),
    ("llm_health", re.compile(
        r"conversation health|context (health|quality|degradi|rot)|session (health|fatigue)|"
        r"how.{0,5} my (conversation|chat|context)|am i (degrading|losing context)|"
        r"chat health|health score|test.*(chat|conversation|context) health|"
        r"my (chat|conversation|context).*(health|score|quality)|"
        r"check.*(chat|conversation|context)|llm health|^conversation[\s!?.]*$",
        re.IGNORECASE,
    )),
    ("disk", re.compile(
        r"disk|storage|space|free up|clean|large files|what.s taking.*(space|room)|"
        r"clear|cache|temp|reclaim|drive|gb free|folder.*(big|large|size)|"
        r"(disk|storage|drive).{0,8}full|full.{0,8}(disk|storage|drive)",
        re.IGNORECASE,
    )),
    ("memory", re.compile(
        r"memory|ram|oom|out of memory|leak|swap|available mem",
        re.IGNORECASE,
    )),
    ("cpu", re.compile(
        r"cpu|processor|core|usage.*high|slow|load|thermal|hot|fan",
        re.IGNORECASE,
    )),
    ("process", re.compile(
        r"process|running|what.s (open|running|using)|top apps?|kill|close|background|"
        r"^what.?s open[\s!?.]*$",
        re.IGNORECASE,
    )),
    ("health", re.compile(
        r"system.*(health|status|doing|look|check|ok\b|fine|strain|load)|"
        r"health.*(check|status|system|report)|"
        r"how.{0,5} my (system|computer|machine|pc|laptop)|"
        r"how.{0,5} the (system|computer|machine)|"
        r"overview|summary|diagnos|scan my|system check|"
        r"^overall[\s!?.]*$|overall health|general health|full (check|scan|report)|"
        r"^(health|system|status)[\s!?.]*$",
        re.IGNORECASE,
    )),
]


def _detect_intent(message: str) -> str:
    """Return the best-matching intent or 'general'."""
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(message):
            return intent
    return "general"


# ---------------------------------------------------------------------------
# Unsupported request handler
# ---------------------------------------------------------------------------

_UNSUPPORTED_SPECIFIC: dict[str, str] = {
    "battery": "I don't have access to battery or power data",
    "charge": "I don't have access to battery or charging data",
    "charg": "I don't have access to battery or charging data",
    "wifi": "I can't check your WiFi connection",
    "wi-fi": "I can't check your WiFi connection",
    "bluetooth": "I don't monitor Bluetooth devices",
    "weather": "I don't have weather data",
    "bright": "I can't control screen brightness",
    "volume": "I can't control audio settings",
    "internet speed": "I don't run speed tests",
    "ping": "I don't run network diagnostics",
    "password": "I don't handle passwords or credentials",
}


def _handle_unsupported(message: str) -> dict:
    msg_lower = message.lower()

    explanation = None
    for keyword, specific_msg in _UNSUPPORTED_SPECIFIC.items():
        if keyword in msg_lower:
            explanation = specific_msg
            break

    if explanation:
        intro = f"{explanation} -- I'm built to monitor your system's internal health."
    else:
        intro = "That's outside what I can do. I'm focused on monitoring your system's internal health."

    lines = [
        intro,
        "",
        "Here's where I can help:",
        "- **Disk** -- storage analysis, cleanup suggestions, largest folders",
        "- **Memory** -- RAM usage, top consumers, optimisation tips",
        "- **CPU** -- processor load, hot cores, what's using it",
        "- **Processes** -- what's running and how much it costs",
        "- **Overall health** -- plain-English system check",
        "",
        "Which of these would be useful right now?",
    ]
    return {
        "intent": "unsupported",
        "response": "\n".join(lines),
        "data": {},
    }


# ---------------------------------------------------------------------------
# Disk analysis
# ---------------------------------------------------------------------------

_CLEANUP_TARGETS: list[dict] = [
    {"name": "Windows Temp", "path": lambda: os.environ.get("TEMP", ""), "platform": "Windows"},
    {"name": "Windows Prefetch", "path": lambda: os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Prefetch"), "platform": "Windows"},
    {"name": "Recycle Bin (approx)", "path": lambda: os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "$Recycle.Bin"), "platform": "Windows"},
    {"name": "npm cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "npm-cache") if platform.system() == "Windows" else str(Path.home() / ".npm"), "platform": "any"},
    {"name": "pip cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "pip" / "cache") if platform.system() == "Windows" else str(Path.home() / ".cache" / "pip"), "platform": "any"},
    {"name": "Windows Update cache", "path": lambda: os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SoftwareDistribution", "Download"), "platform": "Windows"},
    {"name": "Chrome cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cache"), "platform": "Windows"},
    {"name": "VS Code cache", "path": lambda: str(Path.home() / "AppData" / "Roaming" / "Code" / "Cache"), "platform": "Windows"},
    {"name": "Thumbnails cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Explorer"), "platform": "Windows"},
]


def _get_dir_size(path: str, max_depth: int = 3) -> float | None:
    """Get directory size in GB. Returns None if inaccessible."""
    size_bytes = _get_dir_size_bytes(path, max_depth)
    if size_bytes is None:
        return None
    return round(size_bytes / (1024 ** 3), 2)


def _get_dir_size_bytes(path: str, max_depth: int = 3) -> int | None:
    """Get directory size in bytes. Returns None if inaccessible."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False) and max_depth > 0:
                    sub = _get_dir_size_bytes(entry.path, max_depth - 1)
                    if sub is not None:
                        total += sub
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        return None
    return total


def _scan_user_directories() -> list[dict]:
    """Scan major user directories and return sizes. Time-bounded to 5 seconds."""
    home = Path.home()
    targets = [
        "Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music",
        "OneDrive", "AppData",
    ]
    results = []
    scan_start = time.time()
    for name in targets:
        if time.time() - scan_start > 5:
            break
        d = home / name
        if d.exists() and d.is_dir():
            size = _get_dir_size(str(d), max_depth=2)
            if size is not None and size > 0.01:
                results.append({"name": name, "path": str(d), "size_gb": size})
    results.sort(key=lambda x: x["size_gb"], reverse=True)
    return results


def _scan_cleanup_targets() -> list[dict]:
    """Scan known cleanup directories and return sizes. Time-bounded to 5 seconds."""
    current_platform = platform.system()
    results = []
    scan_start = time.time()
    for target in _CLEANUP_TARGETS:
        if time.time() - scan_start > 5:
            break
        if target["platform"] not in ("any", current_platform):
            continue
        path = target["path"]()
        if not path or not os.path.isdir(path):
            continue
        size = _get_dir_size(path, max_depth=2)
        if size is not None and size >= 0.01:
            results.append({
                "name": target["name"],
                "path": path,
                "size_gb": size,
            })
    results.sort(key=lambda x: x["size_gb"], reverse=True)
    return results


_disk_scan_lock = threading.Lock()
_disk_scan_cache: dict[str, tuple[float, list]] = {}
_DISK_CACHE_TTL = 30  # seconds


def _cached_scan(name: str, scan_fn: Callable[[], list]) -> list:
    """Return cached scan results if fresh, otherwise re-scan."""
    now = time.time()
    with _disk_scan_lock:
        # Bound cache size to prevent unbounded growth
        if len(_disk_scan_cache) > 10:
            _disk_scan_cache.clear()
        cached = _disk_scan_cache.get(name)
        if cached and (now - cached[0]) < _DISK_CACHE_TTL:
            return list(cached[1])
    result = scan_fn()
    with _disk_scan_lock:
        _disk_scan_cache[name] = (now, result)
    return result


def _format_size(gb: float) -> str:
    """Format size for display."""
    if gb >= 1.0:
        return f"{gb:.1f} GB"
    mb = gb * 1024
    return f"{mb:.0f} MB"


def _handle_disk(message: str) -> dict:
    try:
        disk = get_disk_metrics()
    except Exception:
        logger.warning("Failed to collect disk metrics for chat", exc_info=True)
        return {"intent": "disk", "response": "I couldn't read disk metrics right now. Try again in a moment.", "data": {}}

    used = disk["used_gb"]
    total = disk["total_gb"]
    free = disk["free_gb"]
    pct = disk["percent"]

    lines = [
        f"Your disk is at **{pct:.1f}%** -- {_format_size(used)} used of {_format_size(total)}, with **{_format_size(free)} free**.",
        "",
    ]

    user_dirs = _cached_scan("user_dirs", _scan_user_directories)
    if user_dirs:
        lines.append("**Your largest folders:**")
        for d in user_dirs[:8]:
            lines.append(f"- {d['name']}: {_format_size(d['size_gb'])}")
        lines.append("")

    cleanup = _cached_scan("cleanup", _scan_cleanup_targets)
    reclaimable = sum(c["size_gb"] for c in cleanup)
    if cleanup:
        lines.append(f"**Cleanup opportunities** (~{_format_size(reclaimable)} reclaimable):")
        for c in cleanup[:6]:
            lines.append(f"- {c['name']}: {_format_size(c['size_gb'])}")
        lines.append("")

    lines.append("**What you can do:**")
    if pct >= 90:
        lines.append("- Your disk is critically full. Prioritize clearing Downloads and temp files.")
    dl = next((d for d in user_dirs if d["name"] == "Downloads" and d["size_gb"] > 1.0), None)
    if dl:
        lines.append(f"- Check Downloads ({_format_size(dl['size_gb'])}) for installers and old files you no longer need.")
    if any(c["name"] == "npm cache" for c in cleanup):
        lines.append("- Run `npm cache clean --force` to clear the npm cache.")
    if any(c["name"] == "pip cache" for c in cleanup):
        lines.append("- Run `pip cache purge` to clear the pip cache.")
    if any(c["name"] == "Windows Temp" for c in cleanup):
        lines.append("- Run Disk Cleanup (cleanmgr) or clear your Temp folder.")
    if any(c["name"] == "Chrome cache" for c in cleanup):
        lines.append("- Clear Chrome browsing data (Settings > Privacy > Clear data).")
    if pct >= 80:
        lines.append("- Consider moving large files (Videos, old projects) to an external drive or cloud storage.")
    lines.append("- Run `Win + R` > `cleanmgr` for Windows Disk Cleanup with system files option.")

    return {
        "intent": "disk",
        "response": "\n".join(lines),
        "data": {
            "disk": disk,
            "user_directories": user_dirs[:8],
            "cleanup_targets": cleanup[:6],
            "reclaimable_gb": round(reclaimable, 2),
        },
    }


# ---------------------------------------------------------------------------
# Memory handler
# ---------------------------------------------------------------------------

def _handle_memory(message: str) -> dict:
    try:
        mem = get_memory_metrics()
        breakdown = get_resource_breakdown()
    except Exception:
        logger.warning("Failed to collect memory metrics for chat", exc_info=True)
        return {"intent": "memory", "response": "I couldn't read memory metrics right now. Try again in a moment.", "data": {}}
    # Unpack after successful collection
    top_ram = breakdown.get("ram", [])

    lines = [
        f"RAM is at **{mem['percent']:.0f}%** -- {mem['used_gb']:.1f} GB used of {mem['total_gb']:.1f} GB, **{mem['available_gb']:.1f} GB available**.",
        "",
    ]

    if top_ram:
        lines.append("**Top memory consumers:**")
        for r in top_ram[:5]:
            lines.append(f"- {r['name']}: {r['display']}")
        lines.append("")

    if mem["percent"] >= 85:
        lines.append("Memory is under pressure.")
    elif mem["percent"] >= 70:
        lines.append("Memory is moderate. You have headroom but not a lot.")
    else:
        lines.append("Memory looks healthy right now.")

    lines.append("")
    lines.append("**Ways to improve:**")

    browser_names = {"Google Chrome", "Microsoft Edge", "Mozilla Firefox", "Safari",
                     "Brave Browser", "Opera", "Vivaldi", "Arc Browser"}
    browser_found = False
    for r in top_ram[:5]:
        if r["name"] in browser_names:
            lines.append(f"- Close unused {r['name']} tabs -- browsers hold memory per tab even in background.")
            browser_found = True
            break
    if not browser_found and top_ram:
        lines.append(f"- Close {top_ram[0]['name']} if you're not using it ({top_ram[0]['display']}).")

    lines.append("- Close apps you're not actively using -- even idle apps hold allocated memory.")
    lines.append("- Restart your computer if uptime is long -- clears leaked memory from background services.")

    if mem["total_gb"] <= 8:
        lines.append(f"- Your machine has {mem['total_gb']:.0f} GB total RAM. With modern apps, that's tight. Consider upgrading to 16 GB if possible.")

    if mem["percent"] >= 70:
        lines.append("- Disable startup apps you don't need (Task Manager > Startup tab).")
        lines.append("- Check for memory-heavy extensions in your browser.")

    return {
        "intent": "memory",
        "response": "\n".join(lines),
        "data": {"memory": mem, "top_consumers": top_ram[:5]},
    }


# ---------------------------------------------------------------------------
# CPU handler
# ---------------------------------------------------------------------------

def _handle_cpu(message: str) -> dict:
    try:
        cpu = get_cpu_metrics()
        breakdown = get_resource_breakdown()
    except Exception:
        logger.warning("Failed to collect CPU metrics for chat", exc_info=True)
        return {"intent": "cpu", "response": "I couldn't read CPU metrics right now. Try again in a moment.", "data": {}}
    top_cpu = breakdown.get("cpu", [])

    lines = [
        f"CPU is at **{cpu['percent']:.0f}%** across {cpu['count_logical']} logical cores.",
        "",
    ]

    per_core = cpu.get("per_core", [])
    hot_cores = [i for i, c in enumerate(per_core) if c >= 80]
    if hot_cores:
        core_strs = [f"Core {i} ({per_core[i]:.0f}%)" for i in hot_cores[:4]]
        lines.append(f"Cores running hot: {', '.join(core_strs)}")
        lines.append("")

    if top_cpu:
        lines.append("**Top CPU consumers:**")
        for c in top_cpu[:5]:
            lines.append(f"- {c['name']}: {c['display']}")
        lines.append("")

    if cpu["percent"] >= 80:
        lines.append("CPU is under heavy load.")
    elif cpu["percent"] >= 50:
        lines.append("CPU is moderately busy but handling it fine.")
    else:
        lines.append("CPU is relaxed right now.")

    lines.append("")
    lines.append("**Ways to improve:**")

    if top_cpu:
        heaviest = top_cpu[0]
        lines.append(f"- {heaviest['name']} is your top CPU user ({heaviest['display']}). Close it if not needed.")

    lines.append("- Close background apps -- even minimized apps can run scheduled tasks and use CPU.")
    lines.append("- Check Task Manager (Ctrl+Shift+Esc) > Startup tab and disable apps you don't need at boot.")
    lines.append("- Power plan: make sure you're on 'Balanced' or 'High Performance' if plugged in.")

    if cpu["percent"] >= 50 and top_cpu:
        browser_names = {"Google Chrome", "Microsoft Edge", "Mozilla Firefox"}
        for c in top_cpu[:3]:
            if c["name"] in browser_names:
                lines.append(f"- {c['name']} tabs with animations or videos use constant CPU. Close idle tabs.")
                break

    if len(hot_cores) >= cpu.get("count_logical", 8) // 2:
        lines.append("- Multiple cores are stressed. A single heavy app may be maxing out threads.")

    return {
        "intent": "cpu",
        "response": "\n".join(lines),
        "data": {"cpu": cpu, "top_consumers": top_cpu[:5]},
    }


# ---------------------------------------------------------------------------
# Process handler
# ---------------------------------------------------------------------------

def _handle_process(message: str) -> dict:
    procs = get_grouped_processes(limit=10)
    lines = ["**Currently running (top by resource usage):**", ""]

    for p in procs:
        cpu_str = f"{p.get('cpu_percent', 0):.0f}% CPU"
        mem_str = f"{p.get('memory_mb', 0):.0f} MB RAM"
        count = p.get("instance_count", 1)
        suffix = f" ({count} instances)" if count > 1 else ""
        lines.append(f"- **{p['name']}**{suffix}: {cpu_str}, {mem_str}")

    lines.append("")
    lines.append("To free resources, close applications you're not actively using. Want me to look at a specific resource -- memory, CPU, or disk?")

    return {
        "intent": "process",
        "response": "\n".join(lines),
        "data": {"processes": procs},
    }


# ---------------------------------------------------------------------------
# Health / overview handler
# ---------------------------------------------------------------------------

def _handle_health(message: str) -> dict:
    from bannin.intelligence.summary import generate_summary
    summary = generate_summary()

    lines = [f"**{summary['headline']}**", ""]
    if summary.get("details"):
        lines.append(summary["details"])
        lines.append("")
    if summary.get("suggestions"):
        lines.append("**Suggestions:**")
        for s in summary["suggestions"]:
            lines.append(f"- {s}")
        lines.append("")

    lines.append("Want me to dig deeper into disk, memory, CPU, or processes?")

    return {
        "intent": "health",
        "response": "\n".join(lines),
        "data": summary,
    }


# ---------------------------------------------------------------------------
# History handler
# ---------------------------------------------------------------------------

def _handle_history(message: str) -> dict:
    """Handle 'what happened while I was away?' queries."""
    try:
        from bannin.analytics.store import AnalyticsStore
        store = AnalyticsStore.get()
        stats = store.get_stats()
        total = stats.get("total_events", 0)

        if total == 0:
            return {
                "intent": "history",
                "response": "I don't have any stored history yet. Events start being recorded once the agent is running.",
                "data": {},
            }

        alerts = store.query(event_type="alert", limit=10)
        sessions = store.query(event_type="session_start", limit=5)
        ollama = store.query(event_type="ollama_model_load", limit=5)

        lines = [f"Here's what I've recorded ({total} total events):", ""]

        if alerts:
            lines.append(f"**Recent alerts ({len(alerts)}):**")
            for a in alerts[:5]:
                ts = a.get("timestamp", "")[:19].replace("T", " ") if a.get("timestamp") else ""
                lines.append(f"- [{a.get('severity', '')}] {a.get('message', '')} ({ts})")
            lines.append("")

        if ollama:
            lines.append("**Ollama activity:**")
            for o in ollama[:3]:
                lines.append(f"- {o.get('message', '')}")
            lines.append("")

        if sessions:
            lines.append(f"**Sessions:** {len(sessions)} session(s) recorded")
            lines.append("")

        by_type = stats.get("by_type", {})
        if by_type:
            type_summary = ", ".join(f"{t}: {c}" for t, c in sorted(by_type.items(), key=lambda x: -x[1])[:5])
            lines.append(f"**Event breakdown:** {type_summary}")

        lines.append("")
        lines.append("Want me to check something specific? I can look at your disk, memory, CPU, or processes.")

        return {
            "intent": "history",
            "response": "\n".join(lines),
            "data": stats,
        }
    except Exception:
        logger.debug("History handler failed", exc_info=True)
        return {
            "intent": "history",
            "response": "I couldn't access the event history. The analytics store may not be initialized yet.",
            "data": {},
        }


# ---------------------------------------------------------------------------
# Ollama handler
# ---------------------------------------------------------------------------

def _handle_ollama(message: str) -> dict:
    """Handle Ollama/local LLM queries."""
    try:
        from bannin.llm.ollama import OllamaMonitor
        ollama = OllamaMonitor.get().get_health()

        if not ollama.get("available"):
            return {
                "intent": "ollama",
                "response": "Ollama doesn't seem to be running right now. Start it with `ollama serve` to enable local model monitoring.",
                "data": ollama,
            }

        models = ollama.get("models", [])
        if not models:
            return {
                "intent": "ollama",
                "response": "Ollama is running but no models are loaded. Load one with `ollama run <model>`.",
                "data": ollama,
            }

        lines = [f"Ollama is running with **{len(models)} model(s)** loaded:", ""]
        for m in models:
            lines.append(f"- **{m.get('name', '')}** ({m.get('parameter_size', '')}, {m.get('quantization', '')})")
            lines.append(f"  VRAM: {m.get('vram_gb', 0):.1f} GB ({m.get('vram_percent', 0):.0f}%)")
            if m.get("expires_at"):
                lines.append(f"  Expires: {m.get('expires_at', '')[:19]}")
            lines.append("")

        vram = ollama.get("vram_pressure", 0)
        if vram >= 80:
            lines.append(f"VRAM pressure is high ({vram:.0f}%). Consider unloading unused models.")
        elif vram >= 50:
            lines.append(f"VRAM usage is moderate ({vram:.0f}%).")
        else:
            lines.append(f"VRAM usage looks healthy ({vram:.0f}%).")

        return {
            "intent": "ollama",
            "response": "\n".join(lines),
            "data": ollama,
        }
    except Exception:
        logger.debug("Ollama handler failed", exc_info=True)
        return {
            "intent": "ollama",
            "response": "I couldn't check Ollama status. It may not be installed or the monitor isn't running.",
            "data": {},
        }


# ---------------------------------------------------------------------------
# LLM health handler
# ---------------------------------------------------------------------------

def _handle_llm_health(message: str) -> dict:
    """Handle conversation health queries -- lists all active sessions individually."""
    try:
        from bannin.llm.aggregator import compute_health

        health = compute_health()

        score = health.get("health_score", 100)
        rating = health.get("rating", "excellent")
        per_source = health.get("per_source", [])

        lines = [f"**Conversation health: {score}/100 ({rating})**"]

        if per_source and len(per_source) > 1:
            lines.append(f"*{len(per_source)} active sources (combined = worst score)*")
            lines.append("")

            for src in per_source:
                src_score = src.get("health_score", 100)
                src_rating = src.get("rating", "excellent")
                lines.append(f"**{src.get('label', 'Unknown')}** -- {src_score}/100 ({src_rating})")
                components = src.get("components", {})
                for name, comp in components.items():
                    label = name.replace("_", " ").title()
                    lines.append(f"  - {label}: {comp.get('score', 100):.0f}/100 -- {comp.get('detail', '')}")
                rec = src.get("recommendation")
                if rec:
                    lines.append(f"  *{rec}*")
                lines.append("")
        else:
            source = health.get("source", "Unknown")
            lines.append(f"*Source: {source}*")
            lines.append("")

            components = health.get("components", {})
            for name, comp in components.items():
                label = name.replace("_", " ").title()
                lines.append(f"- {label}: {comp.get('score', 100):.0f}/100 -- {comp.get('detail', '')}")

        rec = health.get("recommendation")
        if rec:
            lines.append(f"**Recommendation:** {rec}")

        dz = health.get("danger_zone")
        if dz and dz.get("in_danger_zone"):
            lines.append(f"\nYou're past the {dz.get('danger_zone_percent', 80)}% danger zone for {dz.get('model', 'this model')}.")

        return {
            "intent": "llm_health",
            "response": "\n".join(lines),
            "data": health,
        }
    except Exception:
        logger.debug("LLM health handler failed", exc_info=True)
        return {
            "intent": "llm_health",
            "response": "I couldn't compute conversation health right now. The health scoring module may not be initialized.",
            "data": {},
        }


# ---------------------------------------------------------------------------
# General fallback
# ---------------------------------------------------------------------------

def _handle_fallback(message: str) -> dict:
    return {
        "intent": "general",
        "response": (
            "I focus on system health monitoring -- disk, memory, CPU, "
            "processes, and conversation health.\n\n"
            "Try asking about your disk space, RAM usage, CPU load, "
            "running processes, or conversation health."
        ),
        "data": {},
    }


# ---------------------------------------------------------------------------
# Handler dispatch
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Callable[[str], dict]] = {
    "disk": _handle_disk,
    "memory": _handle_memory,
    "cpu": _handle_cpu,
    "process": _handle_process,
    "health": _handle_health,
    "unsupported": _handle_unsupported,
    "history": _handle_history,
    "ollama": _handle_ollama,
    "llm_health": _handle_llm_health,
    "general": _handle_fallback,
}


def chat(message: str) -> dict:
    """Process a chat message and return a response with data.

    Returns:
        {
            "intent": str,
            "response": str (markdown-formatted),
            "data": dict (raw data backing the response),
        }
    """
    message = message.strip()
    if not message:
        return {"intent": "empty", "response": "Ask me anything about your system.", "data": {}}

    # Truncate overly long messages to prevent regex DoS and memory waste
    if len(message) > 2000:
        logger.debug("Chat message truncated from %d to 2000 chars", len(message))
        message = message[:2000]

    intent = _detect_intent(message)
    handler = _HANDLERS.get(intent, _handle_fallback)
    return handler(message)
