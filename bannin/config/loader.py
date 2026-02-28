from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from pathlib import Path

from bannin.log import logger

# Where to fetch the latest config from (GitHub raw URL once project is public)
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/Lakshman-P4/Bannin.dev/main/bannin/config/defaults.json"

# Cache remote config locally so we don't fetch every time
_CACHE_DIR = Path.home() / ".bannin"
_CACHE_FILE = _CACHE_DIR / "platform_config.json"
_CACHE_MAX_AGE = 24 * 3600  # Re-fetch once per day

# In-memory config (loaded once, protected by lock)
_config = None
_config_lock = threading.Lock()


def get_config() -> dict:
    """Get the platform config, using remote values if available.

    Network I/O (_fetch_remote) runs outside the lock to avoid blocking
    all callers for the full HTTP timeout (up to 5s). Double-check pattern
    ensures only one thread populates the cache.
    """
    global _config

    # Fast path: _config transitions None -> dict exactly once and is never
    # mutated after assignment.  Under CPython's GIL the reference read is
    # atomic, so this lock-free check is safe (standard double-check pattern).
    if _config is not None:
        return _config

    with _config_lock:
        # Re-check under lock (another thread may have populated it)
        if _config is not None:
            return _config

        # 1. Start with hardcoded defaults (always works, even offline)
        result = _load_defaults()

        # 2. Try to use cached remote config (fast, no network)
        cached = _load_cache()
        if cached:
            result = _merge(result, cached)

        needs_fetch = _cache_is_stale()

    # 3. Fetch remote config OUTSIDE lock to avoid blocking callers
    if needs_fetch:
        remote = _fetch_remote()
        if remote:
            with _config_lock:
                result = _merge(result, remote)
            _save_cache(remote)

    with _config_lock:
        if _config is None:
            _config = result
        return _config


def get_colab_config() -> dict:
    return get_config().get("colab", {})


def get_kaggle_config() -> dict:
    return get_config().get("kaggle", {})


def _load_defaults() -> dict:
    try:
        defaults_path = Path(__file__).parent / "defaults.json"
        with open(defaults_path, "r") as f:
            return json.load(f)
    except Exception:
        logger.warning("Failed to load defaults.json, using minimal hardcoded config")
        return {
            "colab": {},
            "kaggle": {},
            "thresholds": {},
            "alerts": {},
            "llm_pricing": {},
        }


def _load_cache() -> dict | None:
    try:
        if not _CACHE_FILE.exists():
            return None
        with open(_CACHE_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.debug("Config cache is not a dict, ignoring")
            return None
        return data
    except Exception:
        logger.debug("Failed to load config cache from %s", _CACHE_FILE)
        return None


def _save_cache(data: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        logger.debug("Failed to save config cache to %s", _CACHE_FILE)


def _cache_is_stale() -> bool:
    try:
        if not _CACHE_FILE.exists():
            return True
        age = time.time() - _CACHE_FILE.stat().st_mtime
        return age > _CACHE_MAX_AGE
    except Exception:
        logger.debug("Failed to check config cache staleness")
        return True


def _fetch_remote() -> dict | None:
    """Fetch latest config from GitHub. Returns None on any failure (no internet, timeout, etc.)."""
    if not REMOTE_CONFIG_URL.startswith("https://"):
        logger.warning("Remote config URL is not HTTPS, skipping fetch")
        return None
    try:
        _MAX_CONFIG_BYTES = 1024 * 1024  # 1 MB limit
        req = urllib.request.Request(REMOTE_CONFIG_URL, headers={"User-Agent": "bannin-agent/0.1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read(_MAX_CONFIG_BYTES)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                logger.debug("Remote config is not a dict, ignoring")
                return None
            return data
    except Exception:
        logger.debug("Remote config fetch failed (offline or unreachable)")
        return None


def _merge(base: dict, override: dict, depth: int = 0) -> dict:
    """Deep merge override into base. Override values win.

    Args:
        base: The base dict to merge into.
        override: The override dict whose values win on conflict.
        depth: Current recursion depth. Stops recursing at 10.
    """
    _MAX_MERGE_DEPTH = 10
    result = base.copy()
    for key, value in override.items():
        if key.startswith("_"):
            continue
        if (
            depth < _MAX_MERGE_DEPTH
            and key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _merge(result[key], value, depth=depth + 1)
        else:
            result[key] = value
    return result
