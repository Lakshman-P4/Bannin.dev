"""Progress detection — intercepts tqdm bars and stdout patterns.

Detects long-running task progress from two sources:
1. tqdm progress bars (monkey-patched when inside bannin.watch())
2. stdout text patterns like "Epoch 3/10" or "Step 500/2000"

Each detected progress source becomes a tracked "task" with current/total/percent.
ETA calculation is added in Phase 2e.
"""

from __future__ import annotations

import re
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from bannin.log import logger


class ProgressTracker:
    """Singleton that tracks progress from tqdm and stdout patterns."""

    _instance = None
    _lock = threading.Lock()

    _MAX_TASKS = 500

    def __init__(self) -> None:
        self._tasks: dict[str, dict] = {}
        self._external_ids: dict[str, str] = {}  # name -> task_id for external tasks
        self._data_lock = threading.RLock()  # Reentrant: _scan_stdout -> _register_task both need lock
        self._tqdm_patched = False
        self._stdout_patched = False
        self._original_tqdm_init = None
        self._original_tqdm_update = None
        self._original_tqdm_close = None
        self._original_stdout_write = None
        self._compiled_patterns: list[dict] = []
        self._stdout_patterns = self._load_patterns()
        self._stall_timeout = self._load_stall_timeout()

    @classmethod
    def get(cls) -> "ProgressTracker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.unhook_all()
            cls._instance = None

    def _load_patterns(self) -> list[dict]:
        """Load stdout regex patterns from config."""
        try:
            from bannin.config.loader import get_config
            cfg = get_config().get("intelligence", {}).get("progress", {})
            return cfg.get("stdout_patterns", [])
        except Exception:
            return [
                {"name": "epoch", "regex": r"Epoch\s+(\d+)[/](\d+)", "current_group": 1, "total_group": 2},
                {"name": "step", "regex": r"Step\s+(\d+)[/](\d+)", "current_group": 1, "total_group": 2},
                {"name": "percent", "regex": r"(\d+)%", "current_group": 1, "total_group": None},
            ]

    def _load_stall_timeout(self) -> int:
        try:
            from bannin.config.loader import get_config
            cfg = get_config().get("intelligence", {}).get("progress", {})
            return cfg.get("stall_timeout_seconds", 300)
        except Exception:
            return 300

    # ------------------------------------------------------------------
    # tqdm interception
    # ------------------------------------------------------------------

    def hook_tqdm(self) -> None:
        """Monkey-patch tqdm to report progress to this tracker.

        The entire import-save-patch sequence runs under _data_lock so that
        unhook_tqdm cannot restore originals between the flag flip and the
        actual monkey-patch, which would leave None originals.
        """
        try:
            import tqdm as tqdm_module
            tqdm_cls = tqdm_module.tqdm
        except ImportError:
            return  # tqdm not installed, nothing to hook

        with self._data_lock:
            if self._tqdm_patched:
                return

            tracker = self

            # Save originals under lock
            self._original_tqdm_init = tqdm_cls.__init__
            self._original_tqdm_update = tqdm_cls.update
            self._original_tqdm_close = tqdm_cls.close

            original_init = self._original_tqdm_init
            original_update = self._original_tqdm_update
            original_close = self._original_tqdm_close

            def patched_init(self_tqdm: Any, *args: Any, **kwargs: Any) -> None:
                original_init(self_tqdm, *args, **kwargs)
                # Register this progress bar as a tracked task
                task_id = str(uuid.uuid4())[:8]
                desc = getattr(self_tqdm, "desc", None) or "tqdm progress"
                total = getattr(self_tqdm, "total", None)
                self_tqdm._bannin_task_id = task_id
                tracker._register_task(
                    task_id=task_id,
                    name=str(desc),
                    source="tqdm",
                    total=total,
                )

            def patched_update(self_tqdm: Any, n: int = 1) -> None:
                original_update(self_tqdm, n)
                task_id = getattr(self_tqdm, "_bannin_task_id", None)
                if task_id:
                    current = getattr(self_tqdm, "n", 0)
                    total = getattr(self_tqdm, "total", None)
                    tracker._update_task(task_id, current=current, total=total)

            def patched_close(self_tqdm: Any) -> None:
                task_id = getattr(self_tqdm, "_bannin_task_id", None)
                if task_id:
                    total = getattr(self_tqdm, "total", None)
                    tracker._complete_task(task_id, final_current=total)
                original_close(self_tqdm)

            tqdm_cls.__init__ = patched_init
            tqdm_cls.update = patched_update
            tqdm_cls.close = patched_close
            self._tqdm_patched = True

    def unhook_tqdm(self) -> None:
        """Restore original tqdm methods. Entire restore runs under lock."""
        with self._data_lock:
            if not self._tqdm_patched:
                return
            try:
                import tqdm as tqdm_module
                tqdm_cls = tqdm_module.tqdm
                if self._original_tqdm_init:
                    tqdm_cls.__init__ = self._original_tqdm_init
                if self._original_tqdm_update:
                    tqdm_cls.update = self._original_tqdm_update
                if self._original_tqdm_close:
                    tqdm_cls.close = self._original_tqdm_close
            except ImportError:
                pass
            self._tqdm_patched = False

    # ------------------------------------------------------------------
    # stdout pattern detection
    # ------------------------------------------------------------------

    def hook_stdout(self) -> None:
        """Wrap sys.stdout.write to scan for progress patterns.

        The entire save-compile-patch sequence runs under _data_lock so that
        unhook_stdout cannot restore the original between flag flip and patch.
        """
        with self._data_lock:
            if self._stdout_patched:
                return

            tracker = self
            original_write = sys.stdout.write
            self._original_stdout_write = original_write

            # Compile patterns once
            compiled = []
            for p in self._stdout_patterns:
                try:
                    compiled.append({
                        "name": p["name"],
                        "regex": re.compile(p["regex"]),
                        "current_group": p["current_group"],
                        "total_group": p.get("total_group"),
                    })
                except re.error:
                    pass
            self._compiled_patterns = compiled

            def patched_write(text: str) -> int:
                result = original_write(text)
                # Only scan non-empty text strings
                if isinstance(text, str) and text.strip():
                    tracker._scan_stdout(text)
                return result

            sys.stdout.write = patched_write
            self._stdout_patched = True

    def unhook_stdout(self) -> None:
        """Restore original sys.stdout.write. Entire restore runs under lock."""
        with self._data_lock:
            if not self._stdout_patched:
                return
            if self._original_stdout_write:
                sys.stdout.write = self._original_stdout_write
            self._stdout_patched = False

    def _scan_stdout(self, text: str) -> None:
        """Check text against configured patterns and update tasks."""
        # Bound input length to prevent regex DoS on pathological strings
        if len(text) > 4096:
            text = text[:4096]
        for p in self._compiled_patterns:
            match = p["regex"].search(text)
            if match:
                try:
                    current = int(match.group(p["current_group"]))
                    total = int(match.group(p["total_group"])) if p["total_group"] else None

                    # For percent pattern, convert to 0-100 scale
                    if p["name"] == "percent" and total is None:
                        total = 100

                    task_id = f"stdout_{p['name']}"
                    with self._data_lock:
                        if task_id not in self._tasks:
                            self._register_task(
                                task_id=task_id,
                                name=f"{p['name'].title()} progress (stdout)",
                                source="stdout_pattern",
                                total=total,
                            )
                    self._update_task(task_id, current=current, total=total)
                except (IndexError, ValueError):
                    pass

    # ------------------------------------------------------------------
    # Hook all / unhook all
    # ------------------------------------------------------------------

    def hook_all(self) -> None:
        """Hook both tqdm and stdout."""
        self.hook_tqdm()
        self.hook_stdout()

    def unhook_all(self) -> None:
        """Unhook both tqdm and stdout."""
        self.unhook_tqdm()
        self.unhook_stdout()

    # ------------------------------------------------------------------
    # Task management
    # ------------------------------------------------------------------

    def _evict_old_tasks(self) -> None:
        """Remove oldest completed/stalled tasks when capacity exceeded. Must hold _data_lock."""
        if len(self._tasks) < self._MAX_TASKS:
            return
        # Evict completed first, then stalled, by oldest start time
        evictable = [
            (tid, t) for tid, t in self._tasks.items()
            if t["status"] in ("completed", "stalled")
        ]
        evictable.sort(key=lambda x: x[1]["_start_epoch"])
        to_remove = max(1, len(self._tasks) - self._MAX_TASKS + 50)
        for tid, _ in evictable[:to_remove]:
            del self._tasks[tid]
            # Clean up external name index
            stale_names = [n for n, eid in self._external_ids.items() if eid == tid]
            for n in stale_names:
                del self._external_ids[n]

    def _register_task(
        self, task_id: str, name: str, source: str, total: int | None, pid: int | None = None,
    ) -> None:
        with self._data_lock:
            self._evict_old_tasks()
            self._tasks[task_id] = {
                "task_id": task_id,
                "name": name,
                "source": source,
                "current": 0,
                "total": total,
                "percent": 0.0,
                "elapsed_seconds": 0,
                "eta_seconds": None,
                "eta_human": None,
                "eta_timestamp": None,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "_start_epoch": time.time(),
                "_last_update_epoch": time.time(),
                "status": "running",
                "pid": pid,
            }

    def _calculate_eta(self, task: dict) -> None:
        """Calculate estimated time remaining for a task. Must hold _data_lock."""
        current = task["current"]
        total = task["total"]
        elapsed = task["elapsed_seconds"]

        if not total or total <= 0 or current <= 0 or elapsed <= 0:
            task["eta_seconds"] = None
            task["eta_human"] = None
            task["eta_timestamp"] = None
            return

        # time_remaining = elapsed * (remaining / completed)
        remaining = total - current
        rate = current / elapsed  # items per second
        if rate <= 0:
            task["eta_seconds"] = None
            task["eta_human"] = None
            task["eta_timestamp"] = None
            return

        eta_seconds = round(remaining / rate, 1)
        task["eta_seconds"] = eta_seconds
        task["eta_human"] = _format_duration(eta_seconds)
        task["eta_timestamp"] = _format_wall_clock(eta_seconds)

    def _update_task(self, task_id: str, current: int, total: int | None = None) -> None:
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["current"] = current
            if total is not None:
                task["total"] = total
            task["_last_update_epoch"] = time.time()
            task["elapsed_seconds"] = round(time.time() - task["_start_epoch"], 1)

            # Calculate percent
            if task["total"] and task["total"] > 0:
                task["percent"] = round((current / task["total"]) * 100, 1)
            elif current > 0:
                task["percent"] = None  # Unknown total

            # Calculate ETA
            self._calculate_eta(task)

            # Check for completion
            if task["total"] and current >= task["total"]:
                task["status"] = "completed"
                task["eta_seconds"] = 0
                task["eta_human"] = "done"
                task["eta_timestamp"] = None

    def _complete_task(self, task_id: str, final_current: int | None = None) -> None:
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            if final_current is not None:
                task["current"] = final_current
            task["status"] = "completed"
            task["percent"] = 100.0
            task["elapsed_seconds"] = round(time.time() - task["_start_epoch"], 1)

    def check_stalls(self) -> None:
        """Mark tasks as stalled if no update within the timeout."""
        now = time.time()
        with self._data_lock:
            for task in self._tasks.values():
                if task["status"] == "running":
                    if now - task["_last_update_epoch"] > self._stall_timeout:
                        task["status"] = "stalled"

    def get_tasks(self) -> dict:
        """Get all tracked tasks grouped by status, plus detected training processes."""
        self.check_stalls()
        with self._data_lock:
            all_tasks = list(self._tasks.values())

        # Strip internal fields before returning
        clean = []
        for t in all_tasks:
            clean.append({k: v for k, v in t.items() if not k.startswith("_")})

        active = [t for t in clean if t["status"] == "running"]
        completed = [t for t in clean if t["status"] == "completed"]
        stalled = [t for t in clean if t["status"] == "stalled"]

        # Include detected training processes from background scanner
        detected_tasks: list[dict] = []
        try:
            from bannin.intelligence.training import TrainingDetector
            detected_tasks = TrainingDetector.get().get_detected_tasks()
        except Exception:
            pass

        return {
            "active_tasks": active,
            "completed_tasks": completed,
            "stalled_tasks": stalled,
            "detected_tasks": detected_tasks,
            "total_tracked": len(clean) + len(detected_tasks),
        }

    def get_task(self, task_id: str) -> dict | None:
        """Get a single task by ID."""
        self.check_stalls()
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            return {k: v for k, v in task.items() if not k.startswith("_")}

    def get_task_pid(self, task_id: str) -> int | None:
        """Get the PID associated with a task, if any."""
        with self._data_lock:
            task = self._tasks.get(task_id)
            return task.get("pid") if task else None

    def upsert_external(
        self, name: str, current: int, total: int | None = None, pid: int | None = None,
    ) -> dict:
        """Register or update an externally-reported task. Returns task state dict.

        Used by POST /tasks to accept progress from external scripts via
        bannin.progress(). Upserts by name: if a running task with the same
        name exists, updates it; otherwise creates a new task.

        The entire check-create-update sequence runs under _data_lock to prevent
        race conditions where the task could be evicted between creation and update.
        """
        with self._data_lock:
            task_id = self._external_ids.get(name)
            if task_id and task_id in self._tasks and self._tasks[task_id]["status"] == "running":
                # Update PID if provided (process may have restarted)
                if pid is not None:
                    self._tasks[task_id]["pid"] = pid
            else:
                # Create new task
                task_id = f"ext_{uuid.uuid4().hex[:8]}"
                self._external_ids[name] = task_id
                self._register_task(task_id, name, "external", total, pid=pid)

            # Update within the same lock scope to prevent eviction between create and update
            self._update_task(task_id, current=current, total=total)

            # Return snapshot within lock scope
            task = self._tasks.get(task_id)
            if not task:
                return {}
            return {k: v for k, v in task.items() if not k.startswith("_")}


def _format_duration(seconds: float) -> str:
    """Format seconds as a human-readable duration like '22m 15s' or '1h 5m'."""
    if seconds <= 0:
        return "done"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s" if secs else f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m" if mins else f"{hours}h"


def _format_wall_clock(seconds_from_now: float) -> str:
    """Format as a wall-clock time like '3:47 PM'."""
    target = datetime.now(timezone.utc) + timedelta(seconds=seconds_from_now)
    return target.strftime("%H:%M:%S UTC")
