"""Claude Code session reader -- extracts real token data from JSONL transcripts.

Claude Code stores full session transcripts at:
    ~/.claude/projects/<project-slug>/<session-uuid>.jsonl

Each line is a JSON object. Assistant entries contain message.usage with
real token counts from the Anthropic API:
    input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens

Context window usage per API call = input_tokens + cache_creation + cache_read.
This is the REAL context size -- no estimation needed.

This module reads these files incrementally (binary seek, only new bytes)
and provides real health metrics to replace MCP session token estimation.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from pathlib import Path

from bannin.log import logger


def _path_to_slug(path: str) -> str:
    """Convert a filesystem path to Claude's project slug format.

    e.g. C:\\Users\\laksh\\OneDrive\\Documents\\bannin.dev
         -> C--Users-laksh-OneDrive-Documents-bannin-dev
    """
    return path.replace("\\", "-").replace("/", "-").replace(":", "-").replace(".", "-").rstrip("-")


class ClaudeSessionReader:
    """Reads Claude Code JSONL session files for real token data.

    Discovers the active session file via project slug matching,
    monitors it in a background thread (incremental binary reads),
    and provides structured health data on demand.
    """

    _instance: ClaudeSessionReader | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._data_lock = threading.Lock()
        self._session_file: Path | None = None
        self._file_pos: int = 0

        # State from JSONL parsing
        self._model: str | None = None
        self._claude_session_id: str | None = None
        self._first_timestamp: float | None = None
        self._last_timestamp: float | None = None

        # Message counts
        self._user_messages: int = 0
        self._assistant_messages: int = 0

        # Real token data
        self._latest_context_tokens: int = 0  # Latest API call total input
        self._total_output_tokens: int = 0
        self._total_cache_read: int = 0
        self._total_cache_write: int = 0
        self._context_sizes: deque[int] = deque(maxlen=5000)

        # Content analysis (bounded to 500 unique tool names)
        self._tool_use_counts: dict[str, int] = {}
        self._max_tool_names: int = 500
        self._thinking_chars: int = 0
        self._output_chars: int = 0

        # Background thread
        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def get(cls) -> "ClaudeSessionReader":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            if cls._instance:
                cls._instance.stop()
            cls._instance = None

    def discover_session(self, cwd: str | None = None) -> Path | None:
        """Find the active JSONL session file.

        Tries CWD-based slug matching first, then falls back to the
        most recently modified JSONL across all projects.
        """
        projects_dir = Path.home() / ".claude" / "projects"
        if not projects_dir.is_dir():
            return None

        # CWD-based slug match
        if cwd:
            slug = _path_to_slug(cwd)
            project_dir = projects_dir / slug
            if project_dir.is_dir():
                jsonl_files = sorted(
                    project_dir.glob("*.jsonl"),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                if jsonl_files:
                    return jsonl_files[0]

        # Fallback: most recently modified JSONL across all projects
        # Cap traversal to prevent unbounded I/O on large ~/.claude/projects/
        best: Path | None = None
        best_mtime = 0.0
        projects_scanned = 0
        for project in projects_dir.iterdir():
            if not project.is_dir():
                continue
            projects_scanned += 1
            if projects_scanned > 50:
                break
            for jf in project.glob("*.jsonl"):
                try:
                    mt = jf.stat().st_mtime
                    if mt > best_mtime:
                        best_mtime = mt
                        best = jf
                except OSError:
                    continue
        return best

    def start(self, cwd: str | None = None, interval: float = 10.0) -> None:
        """Start background monitoring of the active session file."""
        # Discover session file outside lock (filesystem I/O can block)
        session_file = self.discover_session(cwd)
        if not session_file:
            return

        with self._data_lock:
            if self._running:
                return
            self._session_file = session_file
            self._running = True

        self._thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        with self._data_lock:
            self._running = False
        self._stop_event.set()

    @property
    def session_file(self) -> Path | None:
        with self._data_lock:
            return self._session_file

    def _monitor_loop(self, interval: float) -> None:
        self._read_new_lines()
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=interval)
            if self._stop_event.is_set():
                break
            self._read_new_lines()

    def _read_new_lines(self) -> None:
        """Incrementally read new bytes from the JSONL file (binary mode)."""
        with self._data_lock:
            sf = self._session_file
            file_pos = self._file_pos
        if not sf or not sf.exists():
            return

        try:
            fsize = sf.stat().st_size
            if fsize <= file_pos:
                return

            with open(sf, "rb") as f:
                f.seek(file_pos)
                # Cap each read to 10MB to prevent memory spikes on huge transcripts
                raw = f.read(10 * 1024 * 1024)

            if not raw:
                return

            # Only process up to the last complete line (ends with newline).
            # The file may be mid-write, so the last partial line is skipped
            # and will be picked up on the next read.
            last_newline = raw.rfind(b"\n")
            if last_newline == -1:
                return  # No complete line yet

            complete = raw[: last_newline + 1]
            with self._data_lock:
                self._file_pos = file_pos + len(complete)

            text = complete.decode("utf-8", errors="replace")
            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    self._process_entry(entry)
                except json.JSONDecodeError:
                    continue
        except Exception:
            logger.debug("JSONL session file read failed", exc_info=True)

    def _parse_timestamp(self, ts: str) -> float | None:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, TypeError):
            return None

    def _process_entry(self, entry: dict) -> None:
        """Process a single JSONL entry and update accumulated state."""
        entry_type = entry.get("type")
        if not entry_type:
            return

        ts_str = entry.get("timestamp")
        ts_epoch = self._parse_timestamp(ts_str) if ts_str else None

        with self._data_lock:
            # Session ID (Claude Code's, not MCP)
            sid = entry.get("sessionId")
            if sid and not self._claude_session_id:
                self._claude_session_id = sid

            # Timestamps
            if ts_epoch:
                if self._first_timestamp is None:
                    self._first_timestamp = ts_epoch
                self._last_timestamp = ts_epoch

            if entry_type == "user":
                self._user_messages += 1

            elif entry_type == "assistant":
                self._assistant_messages += 1
                msg = entry.get("message", {})

                # Model
                model = msg.get("model")
                if model:
                    self._model = model

                # Real token counts from API usage
                usage = msg.get("usage", {})
                if usage:
                    input_t = usage.get("input_tokens", 0)
                    cache_creation = usage.get("cache_creation_input_tokens", 0)
                    cache_read = usage.get("cache_read_input_tokens", 0)
                    output_t = usage.get("output_tokens", 0)

                    # Context size = all tokens sent to the model for this call
                    context_size = input_t + cache_creation + cache_read
                    if context_size > 0:
                        self._latest_context_tokens = context_size
                        self._context_sizes.append(context_size)

                    self._total_output_tokens += output_t
                    self._total_cache_read += cache_read
                    self._total_cache_write += cache_creation

                # Content block analysis
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        bt = block.get("type")
                        if bt == "thinking":
                            t = block.get("thinking", "")
                            if t:
                                self._thinking_chars += len(t)
                        elif bt == "text":
                            t = block.get("text", "")
                            if t:
                                self._output_chars += len(t)
                        elif bt == "tool_use":
                            name = block.get("name", "unknown")
                            if name in self._tool_use_counts or len(self._tool_use_counts) < self._max_tool_names:
                                self._tool_use_counts[name] = (
                                    self._tool_use_counts.get(name, 0) + 1
                                )

    def get_real_health_data(self) -> dict | None:
        """Get real health metrics from the JSONL session.

        Returns None if no assistant messages have been parsed yet.

        Returns dict with:
            source: "claude_jsonl"
            model: str
            claude_session_id: str
            context_tokens: int (latest API call context size)
            context_window: int (model's max context)
            context_percent: float (real context usage)
            total_output_tokens: int (cumulative generation)
            estimated_thinking_tokens: int (~4 chars/token)
            total_cache_read_tokens: int
            total_cache_write_tokens: int
            cache_hit_rate: float (0-100)
            user_messages: int
            assistant_messages: int
            total_messages: int
            tool_use_counts: dict[str, int]
            total_tool_uses: int
            session_duration_seconds: float
            context_growth_rate: int | None (tokens per API call)
            api_calls: int (number of API round-trips)
        """
        # Import outside lock to avoid potential deadlock with import lock
        from bannin.llm.pricing import get_context_window

        with self._data_lock:
            if self._assistant_messages == 0:
                return None

            # Context window from model
            context_window = 200000
            if self._model:
                try:
                    cw = get_context_window(self._model)
                    if cw:
                        context_window = cw
                except Exception:
                    logger.debug("Context window lookup failed for model: %s", self._model)

            # Real context usage
            context_percent = 0.0
            if self._latest_context_tokens > 0:
                context_percent = min(
                    100.0,
                    (self._latest_context_tokens / context_window) * 100,
                )

            # Session duration
            duration = 0.0
            if self._first_timestamp and self._last_timestamp:
                duration = self._last_timestamp - self._first_timestamp

            # Context growth trend
            context_growth_rate = None
            sizes = self._context_sizes
            if len(sizes) >= 3:
                recent = sizes[-5:]
                if len(recent) >= 2:
                    context_growth_rate = round(
                        (recent[-1] - recent[0]) / (len(recent) - 1)
                    )

            # Thinking token estimate (~4 chars per token)
            thinking_tokens = self._thinking_chars // 4

            # Cache efficiency
            total_cache = self._total_cache_read + self._total_cache_write
            cache_hit_rate = 0.0
            if total_cache > 0:
                cache_hit_rate = round(
                    (self._total_cache_read / total_cache) * 100, 1
                )

            return {
                "source": "claude_jsonl",
                "model": self._model,
                "claude_session_id": self._claude_session_id,
                "context_tokens": self._latest_context_tokens,
                "context_window": context_window,
                "context_percent": round(context_percent, 1),
                "total_output_tokens": self._total_output_tokens,
                "estimated_thinking_tokens": thinking_tokens,
                "total_cache_read_tokens": self._total_cache_read,
                "total_cache_write_tokens": self._total_cache_write,
                "cache_hit_rate": cache_hit_rate,
                "user_messages": self._user_messages,
                "assistant_messages": self._assistant_messages,
                "total_messages": self._user_messages + self._assistant_messages,
                "tool_use_counts": dict(self._tool_use_counts),
                "total_tool_uses": sum(self._tool_use_counts.values()),
                "session_duration_seconds": round(duration, 1),
                "output_chars": self._output_chars,
                "thinking_chars": self._thinking_chars,
                "context_sizes": list(sizes[-20:]),
                "context_growth_rate": context_growth_rate,
                "api_calls": len(sizes),
            }
