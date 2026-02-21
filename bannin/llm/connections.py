"""Auto-detect active LLM tools and connections on the system.

Scans running processes for known LLM apps (Claude Desktop, ChatGPT,
Cursor, Windsurf, Ollama, LM Studio, Copilot) and checks MCP session
status. Returns a unified list of detected LLM connections with status.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import psutil

# Process names that indicate LLM tools. Maps exe name -> (display, type).
# type: "app" = desktop app, "server" = inference server, "editor" = AI code editor
_LLM_PROCESSES = {
    "claude.exe": ("Claude Desktop", "app"),
    "claude": ("Claude Desktop", "app"),
    "chatgpt.exe": ("ChatGPT Desktop", "app"),
    "chatgpt": ("ChatGPT Desktop", "app"),
    "copilot.exe": ("Microsoft Copilot", "app"),
    "cursor.exe": ("Cursor", "editor"),
    "cursor": ("Cursor", "editor"),
    "windsurf.exe": ("Windsurf", "editor"),
    "windsurf": ("Windsurf", "editor"),
    "ollama.exe": ("Ollama", "server"),
    "ollama": ("Ollama", "server"),
    "ollama_llama_server.exe": ("Ollama Server", "server"),
    "ollama_llama_server": ("Ollama Server", "server"),
    "llama-server.exe": ("Llama Server", "server"),
    "llama-server": ("Llama Server", "server"),
    "lmstudio.exe": ("LM Studio", "app"),
    "lmstudio": ("LM Studio", "app"),
}

# Dedup: multiple exe names map to the same display name
_DISPLAY_PRIORITY = {
    "Claude Desktop": 1,
    "Cursor": 2,
    "Windsurf": 3,
    "Ollama": 4,
    "ChatGPT Desktop": 5,
    "LM Studio": 6,
    "Microsoft Copilot": 7,
    "Ollama Server": 8,
    "Llama Server": 9,
}


class LLMConnectionScanner:
    """Singleton that periodically scans for LLM processes."""

    _instance: Optional["LLMConnectionScanner"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._data_lock = threading.Lock()
        self._connections: list[dict] = []
        self._last_scan: float = 0
        self._scan_interval = 10  # seconds

    @classmethod
    def get(cls) -> "LLMConnectionScanner":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def get_connections(self) -> list[dict]:
        """Return detected LLM connections, scanning if stale."""
        now = time.time()
        if now - self._last_scan >= self._scan_interval:
            self._scan()
        with self._data_lock:
            return list(self._connections)

    def _scan(self):
        """Scan running processes for LLM tools."""
        found: dict[str, dict] = {}

        try:
            for proc in psutil.process_iter(["name", "pid", "memory_info"]):
                try:
                    name = (proc.info["name"] or "").lower()
                    if name in _LLM_PROCESSES:
                        display, kind = _LLM_PROCESSES[name]
                        if display == "Ollama Server":
                            # Ollama Server implies Ollama is running -- skip dupe
                            if "Ollama" in found:
                                continue
                        mem_mb = 0
                        if proc.info.get("memory_info"):
                            mem_mb = proc.info["memory_info"].rss / (1024 * 1024)
                        # Keep the entry with highest memory (main process)
                        if display not in found or mem_mb > found[display].get("memory_mb", 0):
                            found[display] = {
                                "name": display,
                                "type": kind,
                                "status": "running",
                                "pid": proc.info["pid"],
                                "memory_mb": round(mem_mb, 1),
                            }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

        # Enrich with Ollama model data
        if "Ollama" in found:
            try:
                from bannin.llm.ollama import OllamaMonitor
                health = OllamaMonitor.get().get_health()
                if health.get("available"):
                    models = health.get("models", [])
                    if models:
                        model_names = [m.get("name", "") for m in models]
                        found["Ollama"]["models"] = model_names
                        found["Ollama"]["status"] = "running"
                        found["Ollama"]["detail"] = ", ".join(model_names[:3])
                    else:
                        found["Ollama"]["status"] = "idle"
                        found["Ollama"]["detail"] = "No models loaded"
            except Exception:
                pass

        # Check MCP sessions (pushed from MCP server processes)
        try:
            from bannin.api import get_mcp_sessions
            sessions = get_mcp_sessions()
            for sid, session_data in sessions.items():
                label = session_data.get("client_label", "MCP Session")
                display_name = f"{label} - MCP"
                tool_calls = session_data.get("total_tool_calls", 0)
                duration = session_data.get("session_duration_minutes", 0)
                if tool_calls > 0:
                    detail = f"{tool_calls} tool calls, {duration:.0f} min"
                else:
                    detail = f"{duration:.0f} min"
                mcp_entry = {
                    "name": display_name,
                    "type": "mcp",
                    "status": "connected",
                    "detail": detail,
                    "tool_calls": tool_calls,
                    "session_minutes": duration,
                    "session_id": sid,
                }
                found[display_name] = mcp_entry
        except Exception:
            pass

        # Sort by priority
        connections = sorted(
            found.values(),
            key=lambda c: _DISPLAY_PRIORITY.get(c["name"], 99),
        )

        with self._data_lock:
            self._connections = connections
            self._last_scan = time.time()
