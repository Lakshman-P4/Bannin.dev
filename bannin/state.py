"""Shared mutable state for cross-module access.

Breaks the circular import between api.py and intelligence/llm modules
by providing a neutral home for shared state (MCP sessions, etc.).
Dependencies flow inward: api -> state <- intelligence/llm.
"""

from __future__ import annotations

import threading
import time


# ---------------------------------------------------------------------------
# MCP session data pushed from MCP server processes (keyed by session_id)
# ---------------------------------------------------------------------------

_mcp_sessions: dict[str, dict] = {}
_mcp_session_lock = threading.Lock()
_MCP_SESSION_TTL = 60  # seconds before a session is considered expired


def _expire_sessions() -> None:
    """Remove sessions that haven't pushed data within TTL. Caller holds lock."""
    now = time.time()
    expired = [
        sid for sid, data in _mcp_sessions.items()
        if now - data.get("_last_seen", 0) > _MCP_SESSION_TTL
    ]
    for sid in expired:
        del _mcp_sessions[sid]


def get_mcp_sessions() -> dict[str, dict]:
    """Get all live MCP sessions (keyed by session_id). Expires stale sessions."""
    with _mcp_session_lock:
        _expire_sessions()
        return {
            sid: {k: v for k, v in data.items() if not k.startswith("_")}
            for sid, data in _mcp_sessions.items()
        }


def get_mcp_session_data() -> dict | None:
    """Get the worst (most fatigued) MCP session, or None if no live sessions."""
    sessions = get_mcp_sessions()
    if not sessions:
        return None
    return max(sessions.values(), key=lambda s: s.get("session_fatigue", 0))


_MAX_MCP_SESSIONS = 100


def store_mcp_session(session_id: str, data: dict) -> None:
    """Store or update an MCP session push."""
    with _mcp_session_lock:
        _expire_sessions()
        if session_id not in _mcp_sessions and len(_mcp_sessions) >= _MAX_MCP_SESSIONS:
            return
        entry = dict(data)
        entry["_last_seen"] = time.time()
        _mcp_sessions[session_id] = entry
