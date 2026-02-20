"""Bannin chatbot engine — rule-based, data-driven system health assistant.

Detects user intent from natural language, pulls real metrics from Bannin
collectors, and returns actionable responses. No external LLM dependency.
Handles off-topic and unsupported queries conversationally.
"""

from __future__ import annotations

import os
import platform
import random
import re
import time
from pathlib import Path
from typing import Optional

from bannin.core.collector import get_cpu_metrics, get_memory_metrics, get_disk_metrics
from bannin.core.process import get_grouped_processes, get_resource_breakdown


# ---------------------------------------------------------------------------
# Intent detection — ordered by priority (more specific first)
# ---------------------------------------------------------------------------

_INTENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Social / off-topic — must be checked before "health" (which matches "how's")
    ("greeting", re.compile(
        r"^(hi|hey|hello|yo|sup|what'?s up|howdy|good (morning|afternoon|evening))[\s!?.]*$",
        re.IGNORECASE,
    )),
    ("how_are_you", re.compile(
        r"how are you|how.?re you|how you doing|how do you feel|you doing ok|you good",
        re.IGNORECASE,
    )),
    ("thanks", re.compile(
        r"^(thanks?|thank you|thx|cheers|appreciate|nice one|good job|well done)[\s!?.]*$",
        re.IGNORECASE,
    )),
    ("who_are_you", re.compile(
        r"who are you|what are you|what.?s your name|tell me about yourself|what do you do",
        re.IGNORECASE,
    )),
    # Philosophical / abstract — catch before health so "system" doesn't trigger a health check
    ("philosophical", re.compile(
        r"meaning of life|quality of life|improve my life|make me happy|"
        r"will .+ (help|save|fix) (me|my life|everything)|purpose|"
        r"what should i do with|is it worth|should i give up|"
        r"are you alive|sentient|conscious|do you think|"
        r"can you feel|do you dream|will ai|future of|"
        r"love|friend|lonely|bored|sad|angry|stressed|anxious|depressed",
        re.IGNORECASE,
    )),
    # Unsupported requests
    ("unsupported", re.compile(
        r"battery|charge|charg|wifi|wi-fi|bluetooth|screen bright|volume|"
        r"weather|time|date|alarm|timer|reminder|calendar|email|message|"
        r"play music|open app|launch|install .+|download .+|"
        r"search (for|google|the web)|browse|internet speed|ping|"
        r"screenshot|camera|photo|record|password|login",
        re.IGNORECASE,
    )),
    # System monitoring intents
    ("disk", re.compile(
        r"disk|storage|space|free up|clean|large files|what.s taking.*(space|room)|"
        r"clear|cache|temp|reclaim|full|drive|gb free|folder.*(big|large|size)",
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
        r"process|running|what.s (open|running|using)|top apps?|kill|close|background",
        re.IGNORECASE,
    )),
    ("health", re.compile(
        r"system.*(health|status|doing|look|check|ok\b|fine|strain|load)|"
        r"health.*(check|status|system|report)|"
        r"how.s my (system|computer|machine|pc|laptop)|"
        r"overview|summary|diagnos|scan my|system check",
        re.IGNORECASE,
    )),
    ("help", re.compile(
        r"^(help|what can you|commands|options|\?)[\s!?.]*$",
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
# Conversational / social handlers
# ---------------------------------------------------------------------------

_GREETING_RESPONSES = [
    "Hey there. I'm keeping an eye on your system right now.",
    "Hi. Your watchman is on duty.",
    "Hello. Everything's being monitored as we speak.",
    "Hey. I've got my eye on things.",
]

_GREETING_FOLLOWUPS = [
    "What part of your system would you like to check?",
    "Want me to look at your disk, memory, CPU, or running processes?",
    "Ask me about anything -- disk space, RAM, CPU, or what's running.",
    "How can I help you with your system's health?",
]


def _handle_greeting(message: str) -> dict:
    response = random.choice(_GREETING_RESPONSES)
    followup = random.choice(_GREETING_FOLLOWUPS)
    return {
        "intent": "greeting",
        "response": f"{response}\n\n{followup}",
        "data": {},
    }


_HOW_ARE_YOU_RESPONSES = [
    "Running smoothly over here. No complaints from the watchman.",
    "I'm doing well -- been watching your metrics quietly in the background.",
    "All good on my end. Been keeping track of everything since you started me up.",
    "Can't complain. I don't sleep, so I've been monitoring the whole time.",
    "Doing great. I've been counting your processes and watching memory trends.",
]


def _handle_how_are_you(message: str) -> dict:
    from bannin.intelligence.summary import generate_summary
    summary = generate_summary()

    response = random.choice(_HOW_ARE_YOU_RESPONSES)
    level = summary.get("level", "healthy")

    if level == "healthy":
        bridge = "Your system's doing well too."
    elif level == "busy":
        bridge = "Your system's a bit busy though."
    elif level == "strained":
        bridge = "But your system could use some attention."
    else:
        bridge = "But your system is under strain right now."

    followup = "Want me to dig into anything specific -- disk, memory, CPU, or processes?"

    return {
        "intent": "how_are_you",
        "response": f"{response}\n\n{bridge} {followup}",
        "data": summary,
    }


def _handle_philosophical(message: str) -> dict:
    from bannin.intelligence.summary import generate_summary
    summary = generate_summary()
    mem = get_memory_metrics()
    disk = get_disk_metrics()

    openers = [
        "That's a big question. I'm just a watchman, but I'll tell you what I know.",
        "I think about uptime, not the meaning of life -- but I respect the question.",
        "I'm better with gigabytes than philosophy, but here's my take.",
        "Deep question. I'll stick to what I'm good at, but let me try.",
    ]

    # Build a bridge from the abstract to the concrete
    bridges = []
    if mem["percent"] >= 80:
        bridges.append(f"What I can tell you is that your RAM is at {mem['percent']:.0f}% right now -- fixing that would definitely improve your computer experience.")
    if disk["percent"] >= 80:
        bridges.append(f"Your disk is {disk['percent']:.0f}% full. Clearing some space would make things feel faster and less frustrating.")

    if not bridges:
        bridges.append("Your system is running well right now. One less thing to worry about.")

    followup = "I might not have all the answers, but I can help with the ones about your system. What would you like to check?"

    return {
        "intent": "philosophical",
        "response": f"{random.choice(openers)}\n\n{' '.join(bridges)}\n\n{followup}",
        "data": summary,
    }


def _handle_thanks(message: str) -> dict:
    responses = [
        "Anytime. That's what I'm here for.",
        "No problem. Let me know if you need anything else checked.",
        "You're welcome. I'll keep watching.",
        "Happy to help. I'm here whenever you need a system check.",
    ]
    followup = "Anything else you'd like me to look at?"
    return {
        "intent": "thanks",
        "response": f"{random.choice(responses)}\n\n{followup}",
        "data": {},
    }


def _handle_who_are_you(message: str) -> dict:
    lines = [
        "I'm **Bannin** -- your system's watchman.",
        "",
        "I monitor your computer's health in real time: CPU load, memory pressure, "
        "disk usage, and what processes are consuming your resources. I can predict "
        "out-of-memory crashes before they happen, and I give you specific steps to "
        "improve things.",
        "",
        "I also track LLM API usage (tokens, cost, latency) and monitor cloud "
        "notebooks like Google Colab and Kaggle.",
        "",
        "What would you like me to check for you?",
    ]
    return {
        "intent": "who_are_you",
        "response": "\n".join(lines),
        "data": {},
    }


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

    # Find specific match for a better response
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
    {"name": "Windows Prefetch", "path": lambda: r"C:\Windows\Prefetch", "platform": "Windows"},
    {"name": "Recycle Bin (approx)", "path": lambda: r"C:\$Recycle.Bin", "platform": "Windows"},
    {"name": "npm cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "npm-cache") if platform.system() == "Windows" else str(Path.home() / ".npm"), "platform": "any"},
    {"name": "pip cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "pip" / "cache") if platform.system() == "Windows" else str(Path.home() / ".cache" / "pip"), "platform": "any"},
    {"name": "Windows Update cache", "path": lambda: r"C:\Windows\SoftwareDistribution\Download", "platform": "Windows"},
    {"name": "Chrome cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cache"), "platform": "Windows"},
    {"name": "VS Code cache", "path": lambda: str(Path.home() / "AppData" / "Roaming" / "Code" / "Cache"), "platform": "Windows"},
    {"name": "Thumbnails cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Explorer"), "platform": "Windows"},
]


def _get_dir_size(path: str, max_depth: int = 3) -> Optional[float]:
    """Get directory size in GB. Returns None if inaccessible."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False) and max_depth > 0:
                    sub = _get_dir_size(entry.path, max_depth - 1)
                    if sub is not None:
                        total += int(sub * (1024 ** 3))
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        return None
    return round(total / (1024 ** 3), 2)


def _scan_user_directories() -> list[dict]:
    """Scan major user directories and return sizes."""
    home = Path.home()
    targets = [
        "Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music",
        "OneDrive", "AppData",
    ]
    results = []
    for name in targets:
        d = home / name
        if d.exists() and d.is_dir():
            size = _get_dir_size(str(d), max_depth=2)
            if size is not None and size > 0.01:
                results.append({"name": name, "path": str(d), "size_gb": size})
    results.sort(key=lambda x: x["size_gb"], reverse=True)
    return results


def _scan_cleanup_targets() -> list[dict]:
    """Scan known cleanup directories and return sizes."""
    current_platform = platform.system()
    results = []
    for target in _CLEANUP_TARGETS:
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


def _format_size(gb: float) -> str:
    """Format size for display."""
    if gb >= 1.0:
        return f"{gb:.1f} GB"
    mb = gb * 1024
    return f"{mb:.0f} MB"


def _handle_disk(message: str) -> dict:
    disk = get_disk_metrics()
    used = disk["used_gb"]
    total = disk["total_gb"]
    free = disk["free_gb"]
    pct = disk["percent"]

    lines = [
        f"Your disk is at **{pct:.1f}%** -- {_format_size(used)} used of {_format_size(total)}, with **{_format_size(free)} free**.",
        "",
    ]

    user_dirs = _scan_user_directories()
    if user_dirs:
        lines.append("**Your largest folders:**")
        for d in user_dirs[:8]:
            lines.append(f"- {d['name']}: {_format_size(d['size_gb'])}")
        lines.append("")

    cleanup = _scan_cleanup_targets()
    reclaimable = sum(c["size_gb"] for c in cleanup)
    if cleanup:
        lines.append(f"**Cleanup opportunities** (~{_format_size(reclaimable)} reclaimable):")
        for c in cleanup[:6]:
            lines.append(f"- {c['name']}: {_format_size(c['size_gb'])}")
        lines.append("")

    lines.append("**What you can do:**")
    if pct >= 90:
        lines.append("- Your disk is critically full. Prioritize clearing Downloads and temp files.")
    if any(d["name"] == "Downloads" and d["size_gb"] > 1.0 for d in user_dirs):
        dl = next(d for d in user_dirs if d["name"] == "Downloads")
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
    mem = get_memory_metrics()
    breakdown = get_resource_breakdown()
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
    cpu = get_cpu_metrics()
    breakdown = get_resource_breakdown()
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
# Help handler
# ---------------------------------------------------------------------------

def _handle_help(message: str) -> dict:
    lines = [
        "Here's what I can help with:",
        "",
        '- **"Why is my disk so full?"** -- storage analysis with cleanup suggestions',
        '- **"What\'s eating my memory?"** -- RAM breakdown by application',
        '- **"How\'s my CPU?"** -- processor load and hot cores',
        '- **"What\'s running?"** -- top processes by resource usage',
        '- **"How\'s my system?"** -- overall health check',
        '- **"Help me free up space"** -- actionable disk cleanup guide',
        "",
        "I pull real data from your system -- every answer reflects what's happening right now.",
        "",
        "What would you like to check?",
    ]
    return {
        "intent": "help",
        "response": "\n".join(lines),
        "data": {},
    }


# ---------------------------------------------------------------------------
# General fallback — smarter redirect
# ---------------------------------------------------------------------------

def _handle_general(message: str) -> dict:
    from bannin.intelligence.summary import generate_summary
    summary = generate_summary()
    level = summary.get("level", "healthy")

    # Give a quick status then redirect
    if level in ("strained", "critical"):
        opener = f"I'm not sure what you mean, but I did notice your system is **{level}** right now."
        nudge = "Want me to take a closer look at what's going on?"
    elif level == "busy":
        opener = "I didn't quite catch that, but your system is a little busy at the moment."
        nudge = "I can check your disk, memory, CPU, or running processes -- which one?"
    else:
        opener = "I'm not sure I understood that."
        nudge = "I can help with disk space, memory, CPU, or running processes. What would you like to check?"

    return {
        "intent": "general",
        "response": f"{opener}\n\n{nudge}",
        "data": summary,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

_HANDLERS = {
    "disk": _handle_disk,
    "memory": _handle_memory,
    "cpu": _handle_cpu,
    "process": _handle_process,
    "health": _handle_health,
    "help": _handle_help,
    "greeting": _handle_greeting,
    "how_are_you": _handle_how_are_you,
    "thanks": _handle_thanks,
    "who_are_you": _handle_who_are_you,
    "philosophical": _handle_philosophical,
    "unsupported": _handle_unsupported,
    "general": _handle_general,
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

    intent = _detect_intent(message)
    handler = _HANDLERS.get(intent, _handle_general)
    return handler(message)
