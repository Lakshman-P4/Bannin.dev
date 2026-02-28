"""Process monitoring with background scanning.

On Windows, psutil.process_iter is expensive (~8 seconds for 300+ processes
on a memory-constrained machine). To avoid blocking API responses and burning
CPU, we scan processes in a background thread every 15 seconds (configurable)
and serve cached results to all callers.
"""

from __future__ import annotations

import os
import time
import threading
from collections import defaultdict

import psutil

from bannin.log import logger

_own_pid = os.getpid()

from bannin.core.process_names import (
    get_friendly_name, get_description, is_hidden, should_split,
)

_cpu_primed = False
_cpu_prime_lock = threading.Lock()

# Background scan results — updated every 15 seconds by _bg_scan_loop
_bg_lock = threading.Lock()
_bg_scan_data = []          # raw process list
_bg_grouped_data = []       # grouped + friendly names
_bg_breakdown_data = {"cpu": [], "ram": []}
_bg_count_data = {"total": 0, "running": 0, "sleeping": 0}
_bg_ready = False           # True after first scan completes


def _ensure_cpu_primed() -> None:
    global _cpu_primed
    with _cpu_prime_lock:
        if _cpu_primed:
            return
        for proc in psutil.process_iter(["cpu_percent"]):
            pass
        time.sleep(0.1)
        _cpu_primed = True


_scanner_started = False
_scanner_lock = threading.Lock()
_scanner_stop = threading.Event()
_scanner_thread: threading.Thread | None = None


def start_background_scanner(interval: int = 15) -> None:
    """Start the background process scanner thread. Idempotent."""
    global _scanner_started, _scanner_thread
    with _scanner_lock:
        if _scanner_started:
            return
        _scanner_started = True
        _scanner_stop.clear()
        t = threading.Thread(target=_bg_scan_loop, args=(interval,), daemon=True)
        _scanner_thread = t
    t.start()


def stop_background_scanner() -> None:
    """Signal the background scanner to stop. Used for clean shutdown."""
    global _scanner_started, _scanner_thread
    _scanner_stop.set()
    with _scanner_lock:
        thread = _scanner_thread
        _scanner_started = False
        _scanner_thread = None
    if thread is not None:
        thread.join(timeout=5)


def _bg_scan_loop(interval: int) -> None:
    """Background loop: scan processes, build grouped data, cache it all."""
    global _bg_scan_data, _bg_grouped_data, _bg_breakdown_data, _bg_count_data, _bg_ready

    _ensure_cpu_primed()

    while not _scanner_stop.is_set():
        scan_start = time.time()
        try:
            # 1. Scan all processes (the expensive part)
            attrs = ["pid", "name", "cpu_percent", "memory_percent", "status", "cmdline"]
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

            # 2. Feed training detector
            try:
                from bannin.intelligence.training import TrainingDetector
                TrainingDetector.get().update_from_scan(raw)
            except Exception:
                logger.debug("Training detector update failed", exc_info=True)

            # 3. Build grouped data
            grouped = _build_grouped(raw)

            # 4. Build breakdown
            breakdown = _build_breakdown(grouped)

            # 5. Build count
            running = sum(1 for p in raw if p.get("status") == psutil.STATUS_RUNNING)
            sleeping = sum(1 for p in raw if p.get("status") == psutil.STATUS_SLEEPING)
            count = {"total": len(raw), "running": running, "sleeping": sleeping}

            # 6. Swap in new data atomically
            with _bg_lock:
                _bg_scan_data = raw
                _bg_grouped_data = grouped
                _bg_breakdown_data = breakdown
                _bg_count_data = count
                _bg_ready = True

        except Exception:
            logger.warning("Background process scanner error", exc_info=True)

        elapsed = time.time() - scan_start
        _scanner_stop.wait(timeout=max(0, interval - elapsed))


_total_mem_mb: float = 0.0
_total_mem_lock = threading.Lock()


def _build_grouped(raw: list[dict]) -> list[dict]:
    """Build grouped process list from raw scan data."""
    global _total_mem_mb
    with _total_mem_lock:
        if _total_mem_mb == 0.0:
            _total_mem_mb = psutil.virtual_memory().total / (1024 * 1024)
        total_mem_mb = _total_mem_mb

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
        if len(g["pids"]) < 500:
            g["pids"].append(proc["pid"])

    result = []
    for g in groups.values():
        entry = {
            "name": g["friendly_name"],
            "category": g["category"],
            "cpu_percent": round(g["cpu_percent"], 1),
            "memory_percent": round(g["memory_percent"], 1),
            "memory_mb": round(g["memory_mb"], 1),
            "instance_count": g["instance_count"],
            "pids": g["pids"],
        }
        desc = get_description(g["friendly_name"])
        if desc:
            entry["description"] = desc
        result.append(entry)

    result.sort(key=lambda p: (p["cpu_percent"] + p["memory_percent"]), reverse=True)
    return result


def _build_breakdown(grouped: list[dict]) -> dict:
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

def is_scanner_ready() -> bool:
    """Return True after the background scanner has completed at least one scan."""
    with _bg_lock:
        return _bg_ready


def get_top_processes(limit: int = 10) -> list[dict]:
    """Raw process list for MCP server."""
    limit = max(1, min(limit, 1000))
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
    limit = max(1, min(limit, 1000))
    with _bg_lock:
        return [{**item, "pids": list(item.get("pids", []))} for item in _bg_grouped_data[:limit]]


def get_resource_breakdown() -> dict:
    with _bg_lock:
        return {
            "cpu": [dict(item) for item in _bg_breakdown_data.get("cpu", [])],
            "ram": [dict(item) for item in _bg_breakdown_data.get("ram", [])],
        }


# --- Process kill ---

# System-critical PIDs that must never be killed
_PROTECTED_NAMES: set[str] = {
    "system", "system idle process", "registry", "csrss.exe", "wininit.exe",
    "services.exe", "lsass.exe", "smss.exe", "winlogon.exe", "explorer.exe",
    "dwm.exe", "svchost.exe",
    "kernel_task", "launchd", "windowserver", "loginwindow",
    "systemd", "init",
}


def kill_process(pid: int) -> dict:
    """Attempt to kill a process by PID.

    Returns dict with status, message, and process info.
    Refuses to kill system processes, PID 0, or Bannin itself.
    """
    if pid <= 0:
        return {"status": "error", "message": "Invalid PID"}

    if pid == _own_pid:
        return {"status": "error", "message": "Cannot kill the Bannin agent"}

    try:
        proc = psutil.Process(pid)
        proc_name = proc.name().lower()
        create_time = proc.create_time()

        if proc_name in _PROTECTED_NAMES:
            return {
                "status": "error",
                "message": f"Cannot kill protected system process: {proc.name()}",
            }

        friendly, category = get_friendly_name(proc.name())

        # Re-check identity immediately before terminate (mitigate PID reuse TOCTOU)
        # Verify both name and create_time to detect recycled PIDs
        current_name = proc.name().lower()
        if current_name in _PROTECTED_NAMES:
            return {
                "status": "error",
                "message": f"Cannot kill protected system process: {proc.name()}",
            }
        if proc.create_time() != create_time:
            return {
                "status": "error",
                "message": f"PID {pid} was recycled (process changed identity)",
            }

        proc.terminate()

        # Wait up to 3 seconds for graceful shutdown
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            proc.kill()

        return {
            "status": "ok",
            "message": f"Killed {friendly} (PID {pid})",
            "process": {"pid": pid, "name": friendly, "category": category},
        }

    except psutil.NoSuchProcess:
        return {"status": "error", "message": f"Process {pid} not found"}
    except psutil.AccessDenied:
        return {"status": "error", "message": f"Access denied: cannot kill PID {pid}"}
    except Exception as exc:
        logger.warning("Failed to kill PID %d: %s", pid, exc, exc_info=True)
        return {"status": "error", "message": f"Failed to kill PID {pid}: {exc}"}


def get_child_processes(pid: int, limit: int = 200) -> list[dict]:
    """Get child processes of a given PID with resource usage."""
    limit = max(1, min(limit, 1000))
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []

    total_mem_mb = psutil.virtual_memory().total / (1024 * 1024)
    result = []
    for child in children[:limit]:
        try:
            info = child.as_dict(attrs=["pid", "name", "cpu_percent", "memory_percent", "status"])
            mem_pct = info.get("memory_percent") or 0
            result.append({
                "pid": info["pid"],
                "name": info.get("name", ""),
                "cpu_percent": round(info.get("cpu_percent") or 0, 1),
                "memory_mb": round((mem_pct / 100.0) * total_mem_mb, 1),
                "memory_percent": round(mem_pct, 1),
                "status": info.get("status", ""),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    result.sort(key=lambda p: (p["cpu_percent"] + p["memory_percent"]), reverse=True)
    return result
