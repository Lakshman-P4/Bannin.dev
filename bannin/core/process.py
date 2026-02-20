"""Process monitoring with background scanning.

On Windows, psutil.process_iter is expensive (~8 seconds for 300+ processes
on a memory-constrained machine). To avoid blocking API responses and burning
CPU, we scan processes in a background thread every 15 seconds and serve
cached results to all callers.
"""

import os
import time
import threading
from collections import defaultdict

import psutil

_own_pid = os.getpid()

from bannin.core.process_names import (
    get_friendly_name, is_hidden, should_split,
)

_cpu_primed = False

# Background scan results — updated every 15 seconds by _bg_scan_loop
_bg_lock = threading.Lock()
_bg_scan_data = []          # raw process list
_bg_grouped_data = []       # grouped + friendly names
_bg_breakdown_data = {"cpu": [], "ram": []}
_bg_count_data = {"total": 0, "running": 0, "sleeping": 0}
_bg_ready = False           # True after first scan completes


def _ensure_cpu_primed():
    global _cpu_primed
    if not _cpu_primed:
        for proc in psutil.process_iter(["cpu_percent"]):
            pass
        time.sleep(0.1)
        _cpu_primed = True


def start_background_scanner(interval: int = 15):
    """Start the background process scanner thread."""
    t = threading.Thread(target=_bg_scan_loop, args=(interval,), daemon=True)
    t.start()


def _bg_scan_loop(interval: int):
    """Background loop: scan processes, build grouped data, cache it all."""
    global _bg_scan_data, _bg_grouped_data, _bg_breakdown_data, _bg_count_data, _bg_ready

    _ensure_cpu_primed()

    while True:
        try:
            # 1. Scan all processes (the expensive part)
            attrs = ["pid", "name", "cpu_percent", "memory_percent", "status"]
            raw = []
            for proc in psutil.process_iter(attrs):
                try:
                    info = proc.info
                    if info["pid"] == 0 or info["cpu_percent"] is None:
                        continue
                    if info["memory_percent"] is None:
                        continue
                    raw.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # 2. Build grouped data
            grouped = _build_grouped(raw)

            # 3. Build breakdown
            breakdown = _build_breakdown(grouped)

            # 4. Build count
            running = sum(1 for p in raw if p.get("status") == psutil.STATUS_RUNNING)
            sleeping = sum(1 for p in raw if p.get("status") == psutil.STATUS_SLEEPING)
            count = {"total": len(raw), "running": running, "sleeping": sleeping}

            # 5. Swap in new data atomically
            with _bg_lock:
                _bg_scan_data = raw
                _bg_grouped_data = grouped
                _bg_breakdown_data = breakdown
                _bg_count_data = count
                _bg_ready = True

        except Exception:
            pass

        time.sleep(interval)


def _build_grouped(raw: list) -> list[dict]:
    """Build grouped process list from raw scan data."""
    total_mem_mb = psutil.virtual_memory().total / (1024 * 1024)

    groups = defaultdict(lambda: {
        "friendly_name": "",
        "category": "",
        "cpu_percent": 0.0,
        "memory_mb": 0.0,
        "memory_percent": 0.0,
        "instance_count": 0,
        "pids": [],
    })

    for proc in raw:
        name = proc["name"] or ""
        if is_hidden(name):
            continue

        # Identify Bannin's own process
        if proc["pid"] == _own_pid:
            friendly, category = "Bannin Agent", "Monitoring"
            group_key = friendly
        elif should_split(name):
            friendly, category = get_friendly_name(name)
            group_key = f"{friendly}::{proc['pid']}"
        else:
            friendly, category = get_friendly_name(name)
            group_key = friendly

        g = groups[group_key]
        g["friendly_name"] = friendly
        g["category"] = category
        g["cpu_percent"] += proc["cpu_percent"] or 0
        mem_pct = proc["memory_percent"] or 0
        g["memory_mb"] += (mem_pct / 100.0) * total_mem_mb
        g["memory_percent"] += mem_pct
        g["instance_count"] += 1
        g["pids"].append(proc["pid"])

    result = []
    for g in groups.values():
        result.append({
            "name": g["friendly_name"],
            "category": g["category"],
            "cpu_percent": round(g["cpu_percent"], 1),
            "memory_percent": round(g["memory_percent"], 1),
            "memory_mb": round(g["memory_mb"], 1),
            "instance_count": g["instance_count"],
            "pids": g["pids"],
        })

    result.sort(key=lambda p: (p["cpu_percent"] + p["memory_percent"]), reverse=True)
    return result


def _build_breakdown(grouped: list) -> dict:
    """Build top-3 CPU and RAM breakdown from grouped data."""
    by_cpu = sorted(grouped, key=lambda p: p["cpu_percent"], reverse=True)
    top_cpu = []
    for p in by_cpu[:3]:
        if p["cpu_percent"] > 0:
            top_cpu.append({
                "name": p["name"],
                "value": p["cpu_percent"],
                "display": f"{p['cpu_percent']:.1f}%",
            })

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


# --- Public API (all instant — just reads from cached background data) ---

def get_top_processes(limit: int = 10) -> list[dict]:
    """Raw process list for MCP server."""
    with _bg_lock:
        data = _bg_scan_data

    processes = []
    for info in data:
        processes.append({
            "pid": info["pid"],
            "name": info["name"],
            "cpu_percent": round(info["cpu_percent"] or 0, 1),
            "memory_percent": round(info["memory_percent"] or 0, 1),
            "status": info.get("status", ""),
        })
    processes.sort(key=lambda p: (p["cpu_percent"], p["memory_percent"]), reverse=True)
    return processes[:limit]


def get_process_count() -> dict:
    with _bg_lock:
        return dict(_bg_count_data)


def get_grouped_processes(limit: int = 15) -> list[dict]:
    with _bg_lock:
        return _bg_grouped_data[:limit]


def get_resource_breakdown() -> dict:
    with _bg_lock:
        return dict(_bg_breakdown_data)
