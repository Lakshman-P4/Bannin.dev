"""Action endpoints -- kill process, execute recommendations, disk cleanup."""

from __future__ import annotations

import os
import platform
import secrets
import shutil
import time
import threading
from pathlib import Path

from fastapi import APIRouter, Path as PathParam, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bannin.routes import emit_event, error_response


def _emit_event(event_type: str, severity: str, message: str, data: dict | None = None) -> None:
    """Best-effort analytics emit -- delegates to shared helper."""
    emit_event(event_type, "agent", severity, message, data)

router = APIRouter(tags=["actions"])


# ---------------------------------------------------------------------------
# Confirmation tokens -- prevent accidental kills
# ---------------------------------------------------------------------------

_token_lock = threading.Lock()
_pending_tokens: dict[str, dict] = {}
_TOKEN_TTL = 60  # seconds
_MAX_PENDING_TOKENS = 200


def _generate_token(action: str, target: str) -> str | None:
    """Generate a short-lived confirmation token for a destructive action.

    Returns None if the token store is at capacity.
    """
    token = secrets.token_hex(8)
    with _token_lock:
        now = time.time()
        expired = [k for k, v in _pending_tokens.items() if now - v["created"] > _TOKEN_TTL]
        for k in expired:
            del _pending_tokens[k]
        if len(_pending_tokens) >= _MAX_PENDING_TOKENS:
            return None
        _pending_tokens[token] = {"action": action, "target": target, "created": now}
    return token


def _validate_token(token: str, action: str, target: str) -> bool:
    """Validate and consume a confirmation token."""
    with _token_lock:
        entry = _pending_tokens.pop(token, None)
        if entry is None:
            return False
        if time.time() - entry["created"] > _TOKEN_TTL:
            return False
        return entry["action"] == action and entry["target"] == target


# ---------------------------------------------------------------------------
# Kill process
# ---------------------------------------------------------------------------

class KillRequest(BaseModel):
    """Request body for kill confirmation."""
    confirm_token: str = Field(..., max_length=32)


@router.post("/processes/{pid}/kill/prepare", response_model=None)
def prepare_kill(pid: int = PathParam(ge=1)) -> dict | JSONResponse:
    """Generate a confirmation token for killing a process."""
    import psutil
    try:
        proc = psutil.Process(pid)
        name = proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return error_response(404, "Process not found", f"PID {pid} does not exist or is not accessible")

    from bannin.core.process_names import get_friendly_name
    friendly, category = get_friendly_name(name)

    token = _generate_token("kill", str(pid))
    if not token:
        return error_response(429, "Too many pending confirmations", "Try again shortly")
    return {
        "confirm_token": token,
        "pid": pid,
        "name": friendly,
        "category": category,
        "message": f"Confirm kill of {friendly} (PID {pid})?",
    }


@router.post("/processes/{pid}/kill", response_model=None)
def kill_process_endpoint(pid: int = PathParam(ge=1), body: KillRequest = ...) -> dict | JSONResponse:
    """Kill a process by PID after token confirmation."""
    if not _validate_token(body.confirm_token, "kill", str(pid)):
        return error_response(400, "Invalid or expired confirmation token")

    from bannin.core.process import kill_process
    result = kill_process(pid)

    if result["status"] == "ok":
        _emit_event("process_kill", "warning", result["message"], result.get("process", {}))
        return result
    else:
        status_code = 403 if "Access denied" in result["message"] else 400
        return error_response(status_code, result["message"])


@router.get("/processes/{pid}/children")
def get_children(pid: int = PathParam(ge=1)) -> dict:
    """Get child processes of a given PID."""
    from bannin.core.process import get_child_processes
    children = get_child_processes(pid)
    return {"pid": pid, "children": children, "count": len(children)}


# ---------------------------------------------------------------------------
# Recommendation actions
# ---------------------------------------------------------------------------

class ActionRequest(BaseModel):
    """Request body for executing a recommendation action."""
    action: str = Field(..., max_length=64)
    target: str = Field(default="", max_length=512)
    confirm_token: str = Field(..., max_length=32)


@router.post("/actions/prepare", response_model=None)
def prepare_action(action: str = Query(max_length=64), target: str = Query(default="", max_length=512)) -> dict | JSONResponse:
    """Generate a confirmation token for a recommendation action."""
    if action not in ("kill_group", "cleanup_cache", "dismiss"):
        return error_response(400, f"Unknown action: {action}")
    token = _generate_token(action, target)
    if not token:
        return error_response(429, "Too many pending confirmations", "Try again shortly")
    return {"confirm_token": token, "action": action, "target": target}


@router.post("/actions/execute", response_model=None)
def execute_action(body: ActionRequest) -> dict | JSONResponse:
    """Execute a recommendation action after token confirmation."""
    if not _validate_token(body.confirm_token, body.action, body.target):
        return error_response(400, "Invalid or expired confirmation token")

    if body.action == "dismiss":
        return {"status": "ok", "message": "Recommendation dismissed"}
    elif body.action == "kill_group":
        return _action_kill_group(body.target)
    elif body.action == "cleanup_cache":
        return _action_cleanup_cache(body.target)
    else:
        return error_response(400, f"Unknown action: {body.action}")


def _action_kill_group(target: str) -> dict | JSONResponse:
    """Kill all processes in a named group."""
    from bannin.core.process import get_grouped_processes, kill_process

    procs = get_grouped_processes(limit=50)
    group = next((p for p in procs if p["name"] == target), None)
    if not group:
        return error_response(404, f"Process group '{target}' not found")

    killed = []
    failed = []
    for pid in group.get("pids", []):
        result = kill_process(pid)
        if result["status"] == "ok":
            killed.append(pid)
        else:
            failed.append({"pid": pid, "error": result["message"]})

    _emit_event(
        "action_kill_group", "warning",
        f"Killed {len(killed)}/{len(group.get('pids', []))} processes in {target}",
        {"target": target, "killed": killed, "failed": failed},
    )

    return {
        "status": "ok",
        "message": f"Killed {len(killed)} of {len(group.get('pids', []))} {target} processes",
        "killed": killed,
        "failed": failed,
    }


def _is_allowed_cleanup_target(resolved: str) -> bool:
    """Check if a resolved path is an allowed cleanup target (known cache dirs only)."""
    for target in _SCAN_TARGETS:
        if target["name"] in ("__pycache__", "node_modules"):
            continue
        try:
            path = target["path"]()
            if path and os.path.isdir(path) and str(Path(path).resolve()) == resolved:
                return True
        except Exception:
            continue
    basename = Path(resolved).name
    if basename in ("__pycache__", "node_modules"):
        return True
    return False


def _action_cleanup_cache(target: str) -> dict | JSONResponse:
    """Clean a specific cache directory. Never auto-deletes -- returns size freed."""
    if not target or not os.path.isdir(target):
        return error_response(400, f"Invalid cleanup target: {target}")

    # Safety: reject symlinks to prevent traversal to arbitrary directories
    if os.path.islink(target):
        return error_response(403, "Cleanup target must not be a symlink")

    # Safety: resolve to absolute path, validate against known cache directories
    resolved = str(Path(target).resolve())
    home = str(Path.home().resolve())
    temp_dir = os.environ.get("TEMP", "")
    temp_resolved = str(Path(temp_dir).resolve()) if temp_dir else ""
    if not (resolved.startswith(home + os.sep) or (temp_resolved and resolved.startswith(temp_resolved + os.sep))):
        return error_response(403, "Cleanup restricted to user directories")
    if not _is_allowed_cleanup_target(resolved):
        return error_response(403, "Not a recognized cleanup target")

    freed_bytes = 0
    deleted_count = 0
    errors = []

    try:
        for entry in os.scandir(target):
            try:
                if entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                    os.unlink(entry.path)
                    freed_bytes += size
                    deleted_count += 1
                elif entry.is_dir(follow_symlinks=False):
                    size = _dir_size_bytes(entry.path)
                    shutil.rmtree(entry.path, ignore_errors=True)
                    freed_bytes += size
                    deleted_count += 1
            except (PermissionError, OSError) as exc:
                errors.append(str(exc))
    except (PermissionError, OSError) as exc:
        return error_response(403, f"Cannot access: {exc}")

    freed_gb = round(freed_bytes / (1024 ** 3), 2)
    freed_display = f"{freed_gb:.1f} GB" if freed_gb >= 1 else f"{round(freed_bytes / (1024 ** 2))} MB"

    _emit_event(
        "action_cleanup", "info",
        f"Cleaned {target}: {freed_display} freed",
        {"target": target, "freed_bytes": freed_bytes, "deleted": deleted_count},
    )

    return {
        "status": "ok",
        "message": f"Freed {freed_display} ({deleted_count} items)",
        "freed_bytes": freed_bytes,
        "freed_display": freed_display,
        "errors": errors[:5],
    }


def _dir_size_bytes(path: str, max_depth: int = 10) -> int:
    """Get directory size in bytes. Best-effort, depth-bounded, no exceptions."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False) and max_depth > 0:
                    total += _dir_size_bytes(entry.path, max_depth - 1)
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return total


# ---------------------------------------------------------------------------
# Disk cleanup scan
# ---------------------------------------------------------------------------

_SCAN_TARGETS: list[dict] = [
    {"name": "Windows Temp", "path": lambda: os.environ.get("TEMP", ""), "platform": "Windows", "safety": "safe"},
    {"name": "npm cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "npm-cache") if platform.system() == "Windows" else str(Path.home() / ".npm"), "platform": "any", "safety": "safe"},
    {"name": "pip cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "pip" / "cache") if platform.system() == "Windows" else str(Path.home() / ".cache" / "pip"), "platform": "any", "safety": "safe"},
    {"name": "Chrome cache", "path": lambda: str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cache"), "platform": "Windows", "safety": "safe"},
    {"name": "VS Code cache", "path": lambda: str(Path.home() / "AppData" / "Roaming" / "Code" / "Cache"), "platform": "Windows", "safety": "safe"},
    {"name": "__pycache__", "path": lambda: "", "platform": "any", "safety": "safe"},
    {"name": "node_modules", "path": lambda: "", "platform": "any", "safety": "review"},
]

_MAX_SCAN_TIME = 10  # seconds


@router.get("/disk/cleanup")
def disk_cleanup() -> dict:
    """Scan for cleanup targets with sizes and safety ratings."""
    current_platform = platform.system()
    start = time.time()
    targets = []

    for target in _SCAN_TARGETS:
        if time.time() - start > _MAX_SCAN_TIME:
            break
        if target["platform"] not in ("any", current_platform):
            continue

        # Special handling for __pycache__ and node_modules (scan home)
        if target["name"] in ("__pycache__", "node_modules"):
            found = _find_dirs_under_home(target["name"], max_results=10, max_time=3)
            total_bytes = sum(f["size_bytes"] for f in found)
            if total_bytes > 0:
                targets.append({
                    "name": target["name"],
                    "locations": found,
                    "total_bytes": total_bytes,
                    "total_display": _format_bytes(total_bytes),
                    "safety": target["safety"],
                })
            continue

        path = target["path"]()
        if not path or not os.path.isdir(path):
            continue
        size = _dir_size_bytes(path)
        if size > 0:
            targets.append({
                "name": target["name"],
                "path": path,
                "total_bytes": size,
                "total_display": _format_bytes(size),
                "safety": target["safety"],
            })

    targets.sort(key=lambda t: t["total_bytes"], reverse=True)
    total_reclaimable = sum(t["total_bytes"] for t in targets)

    return {
        "targets": targets,
        "total_reclaimable_bytes": total_reclaimable,
        "total_reclaimable_display": _format_bytes(total_reclaimable),
        "scan_time_seconds": round(time.time() - start, 1),
    }


def _find_dirs_under_home(dirname: str, max_results: int = 10, max_time: float = 3) -> list[dict]:
    """Find directories by name under user home. Time-bounded."""
    home = Path.home()
    results = []
    start = time.time()

    # Only scan known dev directories to stay fast
    scan_roots = [
        home / "Documents",
        home / "Projects",
        home / "repos",
        home / "dev",
        home / "code",
        home / "OneDrive" / "Documents",
    ]

    for root in scan_roots:
        if time.time() - start > max_time:
            break
        if not root.exists():
            continue
        try:
            for entry in root.rglob(dirname):
                # Skip symlinks to prevent traversal outside scan scope
                if entry.is_symlink():
                    continue
                if time.time() - start > max_time:
                    break
                if entry.is_dir():
                    size = _dir_size_bytes(str(entry))
                    if size > 0:
                        results.append({
                            "path": str(entry),
                            "size_bytes": size,
                            "size_display": _format_bytes(size),
                        })
                        if len(results) >= max_results:
                            break
        except (PermissionError, OSError):
            continue
        if len(results) >= max_results:
            break

    results.sort(key=lambda r: r["size_bytes"], reverse=True)
    return results


def _format_bytes(b: int) -> str:
    """Format bytes for display."""
    if b >= 1024 ** 3:
        return f"{b / (1024 ** 3):.1f} GB"
    if b >= 1024 ** 2:
        return f"{b / (1024 ** 2):.0f} MB"
    if b >= 1024:
        return f"{b / 1024:.0f} KB"
    return f"{b} B"
