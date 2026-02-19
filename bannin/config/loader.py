import json
import os
import time
import urllib.request
from pathlib import Path

# Where to fetch the latest config from (GitHub raw URL once project is public)
REMOTE_CONFIG_URL = "https://raw.githubusercontent.com/Lakshman-P4/Bannin.dev/main/bannin/config/defaults.json"

# Cache remote config locally so we don't fetch every time
_CACHE_DIR = Path.home() / ".bannin"
_CACHE_FILE = _CACHE_DIR / "platform_config.json"
_CACHE_MAX_AGE = 24 * 3600  # Re-fetch once per day

# In-memory config (loaded once at import time)
_config = None


def get_config() -> dict:
    """Get the platform config, using remote values if available."""
    global _config
    if _config is not None:
        return _config

    # 1. Start with hardcoded defaults (always works, even offline)
    _config = _load_defaults()

    # 2. Try to use cached remote config (fast, no network)
    cached = _load_cache()
    if cached:
        _config = _merge(_config, cached)

    # 3. Try to fetch fresh remote config (background-friendly)
    if _cache_is_stale():
        remote = _fetch_remote()
        if remote:
            _config = _merge(_config, remote)
            _save_cache(remote)

    return _config


def get_colab_config() -> dict:
    return get_config().get("colab", {})


def get_kaggle_config() -> dict:
    return get_config().get("kaggle", {})


def _load_defaults() -> dict:
    defaults_path = Path(__file__).parent / "defaults.json"
    with open(defaults_path, "r") as f:
        return json.load(f)


def _load_cache() -> dict | None:
    try:
        if not _CACHE_FILE.exists():
            return None
        with open(_CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(data: dict):
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _cache_is_stale() -> bool:
    try:
        if not _CACHE_FILE.exists():
            return True
        age = time.time() - _CACHE_FILE.stat().st_mtime
        return age > _CACHE_MAX_AGE
    except Exception:
        return True


def _fetch_remote() -> dict | None:
    """Fetch latest config from GitHub. Returns None on any failure (no internet, timeout, etc.)."""
    try:
        req = urllib.request.Request(REMOTE_CONFIG_URL, headers={"User-Agent": "bannin-agent/0.1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except Exception:
        return None


def _merge(base: dict, override: dict) -> dict:
    """Deep merge override into base. Override values win."""
    result = base.copy()
    for key, value in override.items():
        if key.startswith("_"):
            continue
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result
