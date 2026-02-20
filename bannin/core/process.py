import time
import threading
from collections import defaultdict

import psutil

from bannin.core.process_names import (
    get_friendly_name, is_hidden, should_split, get_cmdline_label,
)

_cpu_primed = False

# Cache for grouped process data (avoids re-scanning within the same poll cycle)
_grouped_cache = {"data": None, "timestamp": 0}
_CACHE_TTL = 2  # seconds


def get_top_processes(limit: int = 10) -> list[dict]:
    """Original function — returns raw process list (used by MCP server)."""
    global _cpu_primed
    if not _cpu_primed:
        for proc in psutil.process_iter(["cpu_percent"]):
            pass
        time.sleep(0.1)
        _cpu_primed = True

    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            if info["pid"] == 0 or info["cpu_percent"] is None:
                continue
            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": round(info["cpu_percent"], 1),
                "memory_percent": round(info["memory_percent"], 1),
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda p: (p["cpu_percent"], p["memory_percent"]), reverse=True)
    return processes[:limit]


def get_process_count() -> dict:
    total = 0
    running = 0
    sleeping = 0

    for proc in psutil.process_iter(["status"]):
        try:
            total += 1
            status = proc.info["status"]
            if status == psutil.STATUS_RUNNING:
                running += 1
            elif status == psutil.STATUS_SLEEPING:
                sleeping += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "total": total,
        "running": running,
        "sleeping": sleeping,
    }


def _scan_all_processes() -> list[dict]:
    """Scan all processes with extended info (cmdline, create_time, ppid)."""
    global _cpu_primed
    if not _cpu_primed:
        for proc in psutil.process_iter(["cpu_percent"]):
            pass
        time.sleep(0.1)
        _cpu_primed = True

    attrs = ["pid", "name", "cpu_percent", "memory_percent", "status",
             "memory_info", "cmdline", "create_time", "ppid"]
    processes = []
    for proc in psutil.process_iter(attrs):
        try:
            info = proc.info
            if info["pid"] == 0 or info["cpu_percent"] is None:
                continue
            if info["memory_percent"] is None:
                continue
            processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def get_grouped_processes(limit: int = 15) -> list[dict]:
    """Return processes grouped by application with friendly names.

    Grouped apps (browsers, editors) combine CPU/RAM into one row.
    Dev runtimes (python, node) stay split with cmdline descriptions.
    Hidden system processes are filtered out.
    """
    now = time.time()
    if _grouped_cache["data"] is not None and (now - _grouped_cache["timestamp"]) < _CACHE_TTL:
        cached = _grouped_cache["data"]
        return cached[:limit]

    raw = _scan_all_processes()

    # Build groups: key = group_key (friendly_name or friendly_name + cmdline_label)
    groups = defaultdict(lambda: {
        "friendly_name": "",
        "category": "",
        "cpu_percent": 0.0,
        "memory_mb": 0.0,
        "memory_percent": 0.0,
        "instance_count": 0,
        "pids": [],
        "cmdline_label": "",
    })

    total_mem_bytes = psutil.virtual_memory().total

    for proc in raw:
        name = proc["name"] or ""
        if is_hidden(name):
            continue

        friendly, category = get_friendly_name(name)

        if should_split(name):
            # Dev runtimes: keep separate, use cmdline to distinguish
            cmdline = proc.get("cmdline")
            label = get_cmdline_label(cmdline, name)
            group_key = f"{friendly}::{label}" if label else f"{friendly}::{proc['pid']}"
            g = groups[group_key]
            g["cmdline_label"] = label
        else:
            # Normal apps: group all instances together
            group_key = friendly
            g = groups[group_key]

        g["friendly_name"] = friendly
        g["category"] = category
        g["cpu_percent"] += proc["cpu_percent"] or 0
        mem_info = proc.get("memory_info")
        if mem_info:
            g["memory_mb"] += mem_info.rss / (1024 * 1024)
        g["memory_percent"] += proc["memory_percent"] or 0
        g["instance_count"] += 1
        g["pids"].append(proc["pid"])

    # Convert to list and sort
    result = []
    for g in groups.values():
        display_name = g["friendly_name"]
        if g["cmdline_label"]:
            display_name = f"{g['friendly_name']} — {g['cmdline_label']}"

        result.append({
            "name": display_name,
            "category": g["category"],
            "cpu_percent": round(g["cpu_percent"], 1),
            "memory_percent": round(g["memory_percent"], 1),
            "memory_mb": round(g["memory_mb"], 1),
            "instance_count": g["instance_count"],
            "pids": g["pids"],
        })

    result.sort(key=lambda p: (p["cpu_percent"] + p["memory_percent"]), reverse=True)

    _grouped_cache["data"] = result
    _grouped_cache["timestamp"] = now

    return result[:limit]


def get_resource_breakdown() -> dict:
    """Return top 3 CPU and RAM consumers (grouped) for metric card breakdowns."""
    grouped = get_grouped_processes(limit=50)

    # Top 3 by CPU
    by_cpu = sorted(grouped, key=lambda p: p["cpu_percent"], reverse=True)
    top_cpu = []
    for p in by_cpu[:3]:
        if p["cpu_percent"] > 0:
            top_cpu.append({
                "name": p["name"],
                "value": p["cpu_percent"],
                "display": f"{p['cpu_percent']:.1f}%",
            })

    # Top 3 by RAM (show in MB or GB)
    by_ram = sorted(grouped, key=lambda p: p["memory_mb"], reverse=True)
    top_ram = []
    for p in by_ram[:3]:
        if p["memory_mb"] > 0:
            mb = p["memory_mb"]
            display = f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.0f} MB"
            top_ram.append({
                "name": p["name"],
                "value": mb,
                "display": display,
            })

    return {"cpu": top_cpu, "ram": top_ram}


# Known user-task executables (things users explicitly run)
_TASK_EXECUTABLES = {
    "python.exe", "python", "python3", "python3.exe", "pythonw.exe",
    "node.exe", "node", "npm.exe", "npm", "npx.exe", "npx",
    "cargo.exe", "cargo", "rustc.exe", "rustc",
    "java.exe", "java", "javaw.exe",
    "go.exe", "go",
    "ruby.exe", "ruby",
    "dotnet.exe", "dotnet",
    "deno.exe", "deno",
    "bun.exe", "bun",
    "gcc.exe", "gcc", "g++.exe", "g++",
    "make.exe", "make", "cmake.exe", "cmake",
    "pytest.exe", "pytest",
    "jupyter.exe", "jupyter",
    "php.exe", "php",
    "perl.exe", "perl",
}

# Known IDE parent processes
_IDE_PARENTS = {
    "code.exe": "VS Code",
    "code": "VS Code",
    "code - insiders.exe": "VS Code Insiders",
    "cursor.exe": "Cursor",
    "cursor": "Cursor",
    "windsurf.exe": "Windsurf",
    "windsurf": "Windsurf",
    "idea64.exe": "IntelliJ IDEA",
    "idea": "IntelliJ IDEA",
    "pycharm64.exe": "PyCharm",
    "pycharm": "PyCharm",
    "webstorm64.exe": "WebStorm",
    "webstorm": "WebStorm",
    "terminal": "Terminal",
    "windowsterminal.exe": "Windows Terminal",
    "warp": "Warp",
    "iterm2": "iTerm2",
    "cmd.exe": "Command Prompt",
    "powershell.exe": "PowerShell",
    "bash.exe": "Bash",
    "bash": "Bash",
    "zsh": "Zsh",
    "fish": "Fish",
}


def get_detected_tasks() -> list[dict]:
    """Detect recently-started user processes that look like active work.

    Finds python/node/cargo/etc. processes started in the last hour,
    reads their cmdline to show script names, and checks parent process
    to detect IDE-spawned work.
    """
    now = time.time()
    one_hour_ago = now - 3600

    raw = _scan_all_processes()
    tasks = []

    # Build a pid -> name lookup for parent process detection
    pid_name_map = {}
    for proc in raw:
        pid_name_map[proc["pid"]] = proc["name"] or ""

    for proc in raw:
        name = (proc["name"] or "").lower().strip()
        if name not in _TASK_EXECUTABLES:
            continue

        create_time = proc.get("create_time")
        if not create_time or create_time < one_hour_ago:
            continue

        cmdline = proc.get("cmdline") or []
        label = get_cmdline_label(cmdline, name)
        friendly, _ = get_friendly_name(name)

        # Detect parent IDE
        via = ""
        ppid = proc.get("ppid")
        if ppid:
            parent_name = pid_name_map.get(ppid, "")
            # Check parent, and grandparent pattern (IDE -> shell -> process)
            if parent_name.lower() in _IDE_PARENTS:
                via = _IDE_PARENTS[parent_name.lower()]
            else:
                # Try grandparent: IDEs often spawn shell -> process
                try:
                    parent = psutil.Process(ppid)
                    gp_name = parent.parent().name() if parent.parent() else ""
                    if gp_name.lower() in _IDE_PARENTS:
                        via = _IDE_PARENTS[gp_name.lower()]
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    pass

        elapsed = now - create_time
        elapsed_human = _format_elapsed(elapsed)

        display = f"{friendly} — {label}" if label else friendly

        tasks.append({
            "name": display,
            "type": "detected",
            "status": "running",
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_human": elapsed_human,
            "via": via,
            "pid": proc["pid"],
        })

    # Sort by most recently started
    tasks.sort(key=lambda t: t["elapsed_seconds"])
    return tasks


def _format_elapsed(seconds: float) -> str:
    """Format elapsed seconds into human-readable string."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"
