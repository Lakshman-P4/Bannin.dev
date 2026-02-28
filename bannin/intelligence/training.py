"""Training process detection via process scanning.

Detects ML/DL training jobs running on the system by inspecting process
command lines for known training scripts, arguments, and framework imports.
Works in standalone mode (bannin start) without requiring bannin.watch().
"""

from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict

from bannin.log import logger


class TrainingDetector:
    """Singleton that detects training processes from background scan data."""

    _instance: TrainingDetector | None = None
    _lock = threading.Lock()

    _DEFAULT_SCRIPTS: list[str] = [
        r"train\.py", r"train_\w+", r"finetune\w*", r"fine_tune\w*",
        r"run_clm\.py", r"run_mlm\.py", r"run_glue\.py", r"trainer\.py",
        r"run_training\.py", r"run_train\.py",
    ]

    _DEFAULT_ARG_KEYWORDS: list[str] = [
        "train", "training", "fit", "finetune", "fine_tune",
        "--do_train", "--num_train_epochs", "epochs",
    ]

    _DEFAULT_FRAMEWORKS: list[str] = [
        "transformers", "pytorch_lightning", "keras", "tensorflow",
        "accelerate", "deepspeed", "fairseq", "torch.distributed",
        "lightning", "detectron2",
    ]

    def __init__(self) -> None:
        self._tracked: OrderedDict[int, dict] = OrderedDict()
        self._data_lock = threading.Lock()
        self._max_tracked = 100
        self._finished_ttl = 300  # seconds

        # Load config
        try:
            from bannin.config.loader import get_config
            cfg = get_config().get("intelligence", {}).get("training_detection", {})
            self._max_tracked = cfg.get("max_tracked", 100)
            self._finished_ttl = cfg.get("finished_ttl_seconds", 300)
            self._script_patterns = cfg.get("scripts", self._DEFAULT_SCRIPTS)
            self._arg_keywords = cfg.get("arg_keywords", self._DEFAULT_ARG_KEYWORDS)
            self._frameworks = cfg.get("frameworks", self._DEFAULT_FRAMEWORKS)
        except Exception:
            self._script_patterns = list(self._DEFAULT_SCRIPTS)
            self._arg_keywords = list(self._DEFAULT_ARG_KEYWORDS)
            self._frameworks = list(self._DEFAULT_FRAMEWORKS)

        # Pre-compile script name regex
        combined = "|".join(f"(?:{p})" for p in self._script_patterns)
        self._script_re = re.compile(combined, re.IGNORECASE)

    @classmethod
    def get(cls) -> TrainingDetector:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def update_from_scan(self, raw_processes: list[dict]) -> None:
        """Inspect scanned processes for training activity.

        Called by the background process scanner after each scan cycle.
        """
        now = time.time()
        seen_pids: set[int] = set()

        for proc in raw_processes:
            name = (proc.get("name") or "").lower()
            if not name.startswith("python"):
                continue

            pid = proc.get("pid")
            if pid is None:
                continue

            cmdline = proc.get("cmdline")
            if not cmdline:
                continue

            # cmdline is a list of strings from psutil
            if not isinstance(cmdline, (list, tuple)):
                continue

            cmd_str = " ".join(str(arg) for arg in cmdline)

            if not self._is_training(cmdline, cmd_str):
                continue

            seen_pids.add(pid)
            script_name = self._extract_script_name(cmdline)
            cpu_pct = proc.get("cpu_percent") or 0
            mem_pct = proc.get("memory_percent") or 0

            with self._data_lock:
                if pid in self._tracked:
                    entry = self._tracked[pid]
                    entry["cpu_percent"] = round(cpu_pct, 1)
                    entry["memory_percent"] = round(mem_pct, 1)
                    entry["elapsed_seconds"] = round(now - entry["_first_seen"], 1)
                    entry["elapsed_human"] = _format_duration(entry["elapsed_seconds"])
                    entry["status"] = "running"
                    # Move to end (most recently seen)
                    self._tracked.move_to_end(pid)
                else:
                    self._evict_if_needed()
                    self._tracked[pid] = {
                        "name": f"Python training ({script_name})",
                        "via": "cmdline",
                        "pid": pid,
                        "cpu_percent": round(cpu_pct, 1),
                        "memory_percent": round(mem_pct, 1),
                        "elapsed_seconds": 0.0,
                        "elapsed_human": "0s",
                        "status": "running",
                        "_first_seen": now,
                        "_finished_at": None,
                    }

        # Mark missing PIDs as finished, evict expired
        with self._data_lock:
            to_remove: list[int] = []
            for pid, entry in self._tracked.items():
                if entry["status"] == "running" and pid not in seen_pids:
                    entry["status"] = "finished"
                    entry["_finished_at"] = now
                elif entry["status"] == "finished":
                    finished_at = entry.get("_finished_at") or now
                    if now - finished_at > self._finished_ttl:
                        to_remove.append(pid)
            for pid in to_remove:
                del self._tracked[pid]

    def get_detected_tasks(self) -> list[dict]:
        """Return detected training tasks (public fields only)."""
        with self._data_lock:
            return [
                {k: v for k, v in entry.items() if not k.startswith("_")}
                for entry in self._tracked.values()
            ]

    def mark_finished(self, pid: int) -> bool:
        """Mark a detected training process as finished.

        Returns True if the PID was found and updated, False otherwise.
        Thread-safe -- acquires _data_lock internally.
        """
        with self._data_lock:
            entry = self._tracked.get(pid)
            if entry is None:
                return False
            entry["status"] = "finished"
            return True

    def _is_training(self, cmdline: list, cmd_str: str) -> bool:
        """Check if command line indicates a training process."""
        # Check script names in arguments
        for arg in cmdline:
            arg_lower = str(arg).lower()
            # Strip path separators to match just the filename
            basename = arg_lower.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            if self._script_re.search(basename):
                return True

        # Check arg keywords
        cmd_lower = cmd_str.lower()
        for kw in self._arg_keywords:
            # Match as whole word or flag to reduce false positives
            if kw.startswith("--"):
                if kw in cmd_lower:
                    return True
            elif re.search(r"(?:^|[\s/\\-])" + re.escape(kw) + r"(?:$|[\s/\\.])", cmd_lower):
                return True

        # Check framework imports: only after -m flag (python -m <framework>)
        for i, arg in enumerate(cmdline):
            if str(arg) == "-m" and i + 1 < len(cmdline):
                module_name = str(cmdline[i + 1]).lower()
                for fw in self._frameworks:
                    if module_name == fw or module_name.startswith(fw + "."):
                        return True
                break  # Only check the first -m argument

        return False

    def _extract_script_name(self, cmdline: list) -> str:
        """Extract a human-readable script name from the command line."""
        for arg in cmdline:
            arg_str = str(arg)
            if arg_str.endswith(".py"):
                basename = arg_str.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                return basename
        # Fall back to module name for -m invocations
        for i, arg in enumerate(cmdline):
            if str(arg) == "-m" and i + 1 < len(cmdline):
                return str(cmdline[i + 1])
        return "unknown"

    def _evict_if_needed(self) -> None:
        """Evict oldest entries when over capacity. Must hold _data_lock."""
        while len(self._tracked) >= self._max_tracked:
            # Evict finished first, then oldest running
            finished = [
                pid for pid, e in self._tracked.items()
                if e["status"] == "finished"
            ]
            if finished:
                del self._tracked[finished[0]]
            else:
                # Remove oldest entry
                self._tracked.popitem(last=False)


def _format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds <= 0:
        return "0s"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m = s // 60
    s = s % 60
    if m < 60:
        return f"{m}m {s}s" if s else f"{m}m"
    h = m // 60
    m = m % 60
    return f"{h}h {m}m" if m else f"{h}h"
