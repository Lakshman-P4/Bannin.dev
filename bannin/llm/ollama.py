"""Ollama local LLM monitor -- auto-detects and tracks locally running models.

Zero-config passive monitoring: detects Ollama at localhost:11434,
polls /api/ps for loaded models, VRAM allocation, and context length.
Graceful degradation: if Ollama is not running, returns empty results.
"""

import json
import threading
import time
import urllib.error
import urllib.request
from typing import Optional


class OllamaMonitor:
    """Singleton that polls Ollama for loaded model info on a background thread."""

    _instance: Optional["OllamaMonitor"] = None
    _lock = threading.Lock()

    def __init__(self, host: str | None = None, poll_interval: int = 15):
        self._host = host or self._resolve_host()
        self._poll_interval = poll_interval
        self._data_lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

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
    def reset(cls):
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
            return env_host.rstrip("/")
        try:
            from bannin.config.loader import get_config
            cfg = get_config()
            host = cfg.get("ollama", {}).get("host")
            if host:
                return host.rstrip("/")
        except Exception:
            pass
        return "http://localhost:11434"

    def start(self):
        """Start background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop background polling."""
        self._running = False

    def _poll_loop(self):
        """Background loop: check Ollama every N seconds."""
        while self._running:
            try:
                self._poll_once()
            except Exception:
                with self._data_lock:
                    self._is_available = False
                    self._models = []
            time.sleep(self._poll_interval)

    def _poll_once(self):
        """Single poll of Ollama /api/ps endpoint."""
        url = f"{self._host}/api/ps"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
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

    def _emit_model_changes(self, old_names: set[str], current_names: set[str]):
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
            pass

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
