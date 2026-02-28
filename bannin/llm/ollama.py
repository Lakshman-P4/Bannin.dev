"""Ollama local LLM monitor -- auto-detects and tracks locally running models.

Zero-config passive monitoring: detects Ollama at localhost:11434,
polls /api/ps for loaded models, VRAM allocation, and context length.
Graceful degradation: if Ollama is not running, returns empty results.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from bannin.log import logger


class OllamaMonitor:
    """Singleton that polls Ollama for loaded model info on a background thread."""

    _instance: OllamaMonitor | None = None
    _lock = threading.Lock()

    def __init__(self, host: str | None = None, poll_interval: int = 15) -> None:
        self._host_override = host
        self._host: str | None = host  # Lazy-resolved on first use if None
        self._poll_interval = max(1, poll_interval)
        self._data_lock = threading.Lock()
        self._running = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Cached state
        self._is_available = False
        self._models: list[dict] = []
        self._last_poll: float = 0
        self._previous_model_names: set[str] = set()

    @classmethod
    def get(cls) -> "OllamaMonitor":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop()
            cls._instance = None

    def _resolve_host(self) -> str:
        """Resolve Ollama host from env var or config, defaulting to localhost:11434."""
        import os
        env_host = os.environ.get("OLLAMA_HOST")
        if env_host:
            if not env_host.startswith("http"):
                env_host = f"http://{env_host}"
            host = env_host.rstrip("/")
        else:
            host = None
            try:
                from bannin.config.loader import get_config
                cfg = get_config()
                host = cfg.get("ollama", {}).get("host")
                if host:
                    host = host.rstrip("/")
            except Exception:
                logger.debug("Config unavailable for Ollama host, using default")

        if not host:
            host = "http://localhost:11434"

        # SSRF mitigation: warn if resolved host is not localhost
        self._validate_host_locality(host)

        return host

    @staticmethod
    def _validate_host_locality(host: str) -> None:
        """Warn if the Ollama host resolves to a non-local address.

        We do not block remote hosts since users may intentionally connect
        to a remote Ollama instance, but we log a warning so the operator
        is aware of the security implication.
        """
        from urllib.parse import urlparse
        import socket

        _LOCAL_ADDRS = {"127.0.0.1", "::1", "localhost"}

        try:
            parsed = urlparse(host)
            hostname = parsed.hostname or ""
            if hostname.lower() in _LOCAL_ADDRS:
                return
            # Resolve to check if it maps to a loopback address
            try:
                resolved = socket.getaddrinfo(hostname, parsed.port or 11434)
                resolved_ips = {addr[4][0] for addr in resolved}
                loopback = {"127.0.0.1", "::1"}
                if resolved_ips & loopback:
                    return
            except socket.gaierror:
                pass
            logger.warning(
                "Ollama host '%s' resolves to a non-local address. "
                "Requests will be sent to a remote server. "
                "If this is unintentional, set OLLAMA_HOST to localhost.",
                host,
            )
        except Exception:
            logger.debug("Failed to validate Ollama host locality")

    def start(self) -> None:
        """Start background polling thread.

        Resolves the Ollama host here (outside the class-level singleton lock)
        to avoid blocking other callers during DNS resolution.
        """
        # Lazy host resolution outside data lock (DNS can block for seconds)
        if self._host is None:
            self._host = self._resolve_host()
        with self._data_lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background polling."""
        with self._data_lock:
            self._running = False
        self._stop_event.set()

    def _poll_loop(self) -> None:
        """Background loop: check Ollama every N seconds."""
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception:
                logger.warning("Ollama poll loop error", exc_info=True)
                with self._data_lock:
                    self._is_available = False
                    self._models = []
            self._stop_event.wait(timeout=self._poll_interval)

    def _poll_once(self) -> None:
        """Single poll of Ollama /api/ps endpoint."""
        if not self._host:
            return
        url = f"{self._host}/api/ps"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read(1024 * 1024).decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError):
            with self._data_lock:
                self._is_available = False
                old_models = self._previous_model_names.copy()
                self._models = []
                self._previous_model_names = set()

            # Emit unload events for models that were previously loaded
            if old_models:
                self._emit_model_changes(old_models, set())
            return

        raw_models = data.get("models", [])
        models = []
        for m in raw_models:
            details = m.get("details", {})
            size_vram = m.get("size_vram", 0)
            size_total = m.get("size", 0)
            vram_percent = round((size_vram / size_total) * 100, 1) if size_total > 0 else 0

            models.append({
                "name": m.get("name", "unknown"),
                "model": m.get("model", ""),
                "family": details.get("family", ""),
                "parameter_size": details.get("parameter_size", ""),
                "quantization": details.get("quantization_level", ""),
                "size_vram_bytes": size_vram,
                "size_vram_gb": round(size_vram / (1024 ** 3), 2),
                "size_total_bytes": size_total,
                "size_total_gb": round(size_total / (1024 ** 3), 2),
                "vram_percent": vram_percent,
                "digest": m.get("digest", ""),
                "expires_at": m.get("expires_at", ""),
            })

        current_names = {m["name"] for m in models}

        with self._data_lock:
            old_names = self._previous_model_names.copy()
            self._is_available = True
            self._models = models
            self._last_poll = time.time()
            self._previous_model_names = current_names

        # Emit load/unload events
        self._emit_model_changes(old_names, current_names)

    def _emit_model_changes(self, old_names: set[str], current_names: set[str]) -> None:
        """Emit analytics events for model loads and unloads."""
        try:
            from bannin.analytics.pipeline import EventPipeline
            pipeline = EventPipeline.get()

            for name in current_names - old_names:
                pipeline.emit({
                    "type": "ollama_model_load",
                    "source": "ollama",
                    "severity": "info",
                    "message": f"Ollama model loaded: {name}",
                    "data": {"model": name},
                })
            for name in old_names - current_names:
                pipeline.emit({
                    "type": "ollama_model_unload",
                    "source": "ollama",
                    "severity": "info",
                    "message": f"Ollama model unloaded: {name}",
                    "data": {"model": name},
                })
        except Exception:
            logger.debug("Failed to emit Ollama model change events")

    # --- Public API ---

    def is_running(self) -> bool:
        """Whether Ollama was detected and responding."""
        with self._data_lock:
            return self._is_available

    def get_models(self) -> list[dict]:
        """Currently loaded models with VRAM, context, and expiry info."""
        with self._data_lock:
            return list(self._models)

    def get_health(self) -> dict:
        """Ollama health summary: availability, VRAM pressure, model info."""
        with self._data_lock:
            if not self._is_available:
                return {
                    "available": False,
                    "models": [],
                    "vram_pressure": 0.0,
                    "message": "Ollama not detected",
                }

            models = list(self._models)

        if not models:
            return {
                "available": True,
                "models": [],
                "vram_pressure": 0.0,
                "message": "Ollama running, no models loaded",
            }

        # VRAM pressure = max vram_percent across loaded models
        max_vram = max(m["vram_percent"] for m in models)
        total_vram_gb = sum(m["size_vram_gb"] for m in models)

        model_summaries = []
        for m in models:
            model_summaries.append({
                "name": m["name"],
                "family": m["family"],
                "parameter_size": m["parameter_size"],
                "quantization": m["quantization"],
                "vram_gb": m["size_vram_gb"],
                "vram_percent": m["vram_percent"],
                "expires_at": m["expires_at"],
            })

        return {
            "available": True,
            "models": model_summaries,
            "model_count": len(models),
            "total_vram_gb": round(total_vram_gb, 2),
            "vram_pressure": max_vram,
            "message": f"{len(models)} model(s) loaded, {total_vram_gb:.1f} GB VRAM",
        }
