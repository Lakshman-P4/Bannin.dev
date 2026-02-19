import os
import time
import shutil

import psutil

from bannin.config.loader import get_colab_config

_session_start_time = time.time()


def _build_tiers() -> dict:
    """Build tier limits from remote config, falling back to defaults."""
    cfg = get_colab_config().get("tiers", {})
    tiers = {}
    for tier_name, defaults in [
        ("free",  {"max_session_hours": 12, "idle_timeout_min": 90,  "disk_gb": 110, "ram_gb": 13, "concurrent_sessions": 2, "background_execution": False}),
        ("pro",   {"max_session_hours": 24, "idle_timeout_min": 180, "disk_gb": 150, "ram_gb": 26, "concurrent_sessions": 3, "background_execution": False}),
        ("pro+",  {"max_session_hours": 24, "idle_timeout_min": 180, "disk_gb": 200, "ram_gb": 53, "concurrent_sessions": 5, "background_execution": True}),
    ]:
        t = cfg.get(tier_name, defaults)
        tiers[tier_name] = {
            "max_session": t.get("max_session_hours", defaults["max_session_hours"]) * 3600,
            "idle_timeout": t.get("idle_timeout_min", defaults["idle_timeout_min"]) * 60,
            "disk_gb": t.get("disk_gb", defaults["disk_gb"]),
            "ram_gb": t.get("ram_gb", defaults["ram_gb"]),
            "concurrent": t.get("concurrent_sessions", defaults["concurrent_sessions"]),
            "background_exec": t.get("background_execution", defaults["background_execution"]),
        }
    return tiers


TIERS = _build_tiers()

# GPU VRAM limits (usable VRAM after overhead)
GPU_SPECS = {
    "T4":   {"vram_gb": 15, "architecture": "Turing",        "cuda_cores": 2560, "tensor_cores": 320,  "retired": False},
    "L4":   {"vram_gb": 22.5, "architecture": "Ada Lovelace", "cuda_cores": 7424, "tensor_cores": 232,  "retired": False},
    "V100": {"vram_gb": 16, "architecture": "Volta",          "cuda_cores": 5120, "tensor_cores": 640,  "retired": True},
    "P100": {"vram_gb": 16, "architecture": "Pascal",         "cuda_cores": 3584, "tensor_cores": 0,    "retired": True},
    "K80":  {"vram_gb": 12, "architecture": "Kepler",         "cuda_cores": 2496, "tensor_cores": 0,    "retired": True},
    "A100": {"vram_gb": 40, "architecture": "Ampere",         "cuda_cores": 6912, "tensor_cores": 432,  "retired": False},
}

# Compute unit burn rates (CU per hour)
GPU_CU_RATES = {
    "T4": 1.96, "L4": 4.82, "A100": 13.08, "V100": 5.0, "P100": 1.96,
    "cpu": 0.07, "cpu_highram": 0.14, "tpu_v2": 1.76,
}

# Hard limits
MAX_NOTEBOOK_SIZE_MB = 20
MAX_FILE_UPLOAD_GB = 2
MAX_FILE_DOWNLOAD_MB = 100


def get_colab_metrics() -> dict:
    tier = _detect_tier()
    return {
        "platform": "colab",
        "tier": tier,
        "session": _get_session_info(tier),
        "gpu": _get_gpu_info(),
        "ram": _get_ram_info(tier),
        "storage": _get_storage_info(tier),
        "drive": _get_drive_info(),
        "concurrent_sessions": TIERS[tier]["concurrent"],
        "background_execution": TIERS[tier]["background_exec"],
        "limits": _get_hard_limits(),
        "warnings": _generate_warnings(tier),
    }


def _detect_tier() -> str:
    total_ram_gb = psutil.virtual_memory().total / (1024**3)
    if total_ram_gb > 40:
        return "pro+"
    if total_ram_gb > 16:
        return "pro"
    return "free"


def _get_session_info(tier: str) -> dict:
    elapsed = time.time() - _session_start_time
    tier_info = TIERS[tier]
    max_session = tier_info["max_session"]
    idle_timeout = tier_info["idle_timeout"]
    remaining = max(0, max_session - elapsed)

    return {
        "elapsed_seconds": round(elapsed),
        "elapsed_human": _format_duration(elapsed),
        "max_session_seconds": max_session,
        "max_session_human": _format_duration(max_session),
        "remaining_seconds": round(remaining),
        "remaining_human": _format_duration(remaining),
        "percent_used": round((elapsed / max_session) * 100, 1),
        "idle_timeout_seconds": idle_timeout,
        "idle_timeout_human": _format_duration(idle_timeout),
    }


def _get_gpu_info() -> dict:
    gpu_name = None
    gpu_memory_total_gb = None
    gpu_memory_used_gb = None
    gpu_memory_free_gb = None
    gpu_memory_percent = None
    gpu_utilization = None
    gpu_temperature = None
    gpu_power_watts = None

    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        gpu_name = name

        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        gpu_memory_total_gb = round(mem.total / (1024**3), 2)
        gpu_memory_used_gb = round(mem.used / (1024**3), 2)
        gpu_memory_free_gb = round(mem.free / (1024**3), 2)
        gpu_memory_percent = round(mem.used / mem.total * 100, 1)

        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_utilization = util.gpu

        try:
            gpu_temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            pass

        try:
            gpu_power_watts = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000, 1)
        except Exception:
            pass
    except Exception:
        pass

    # Fallback: check env var
    if gpu_name is None:
        colab_gpu = os.environ.get("COLAB_GPU", "")
        if colab_gpu:
            gpu_name = f"GPU (env: {colab_gpu})"

    # Match to known specs
    specs = None
    cu_per_hour = None
    if gpu_name:
        for key, info in GPU_SPECS.items():
            if key.lower() in gpu_name.lower():
                specs = info
                cu_per_hour = GPU_CU_RATES.get(key)
                break

    return {
        "assigned": gpu_name is not None,
        "name": gpu_name,
        "memory_total_gb": gpu_memory_total_gb,
        "memory_used_gb": gpu_memory_used_gb,
        "memory_free_gb": gpu_memory_free_gb,
        "memory_percent": gpu_memory_percent,
        "utilization_percent": gpu_utilization,
        "temperature_c": gpu_temperature,
        "power_watts": gpu_power_watts,
        "known_vram_limit_gb": specs["vram_gb"] if specs else None,
        "architecture": specs["architecture"] if specs else None,
        "cuda_cores": specs["cuda_cores"] if specs else None,
        "tensor_cores": specs["tensor_cores"] if specs else None,
        "compute_units_per_hour": cu_per_hour,
    }


def _get_ram_info(tier: str) -> dict:
    mem = psutil.virtual_memory()
    expected_limit = TIERS[tier]["ram_gb"]
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "percent": mem.percent,
        "expected_limit_gb": expected_limit,
        "swap_total_gb": round(psutil.swap_memory().total / (1024**3), 2),
        "swap_used_gb": round(psutil.swap_memory().used / (1024**3), 2),
        "note": "If RAM is exceeded, the runtime crashes and all state is lost.",
    }


def _get_storage_info(tier: str) -> dict:
    content_dir = "/content"
    expected_disk_gb = TIERS[tier]["disk_gb"]
    result = {
        "content_dir": content_dir,
        "expected_limit_gb": expected_disk_gb,
        "total_gb": None,
        "used_gb": None,
        "free_gb": None,
        "percent": None,
        "ephemeral": True,
        "note": "All files in /content are lost when the session ends. Mount Google Drive for persistence.",
    }

    try:
        usage = shutil.disk_usage(content_dir)
        result["total_gb"] = round(usage.total / (1024**3), 2)
        result["used_gb"] = round(usage.used / (1024**3), 2)
        result["free_gb"] = round(usage.free / (1024**3), 2)
        result["percent"] = round(usage.used / usage.total * 100, 1)
    except Exception:
        pass

    return result


def _get_drive_info() -> dict:
    mounted = os.path.isdir("/content/drive/MyDrive")
    drive_usage = None
    if mounted:
        try:
            usage = shutil.disk_usage("/content/drive/MyDrive")
            drive_usage = {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent": round(usage.used / usage.total * 100, 1),
            }
        except Exception:
            pass

    return {
        "mounted": mounted,
        "usage": drive_usage,
        "note": "Google Drive has I/O quotas. Folders with >10,000 files may fail." if mounted else "Mount Drive to save checkpoints: drive.mount('/content/drive')",
    }


def _get_hard_limits() -> dict:
    cpu_count = psutil.cpu_count(logical=True)
    return {
        "max_notebook_size_mb": MAX_NOTEBOOK_SIZE_MB,
        "max_file_upload_gb": MAX_FILE_UPLOAD_GB,
        "max_file_download_mb": MAX_FILE_DOWNLOAD_MB,
        "cpu_cores": cpu_count,
        "inbound_connections": False,
        "ssh_access": _detect_tier() != "free",
        "root_access": True,
        "prohibited": [
            "Cryptocurrency mining",
            "Remote desktop / SSH tunnels (free tier)",
            "File hosting / web serving",
            "Torrent / P2P downloads",
        ],
    }


def _generate_warnings(tier: str) -> list[str]:
    warnings = []

    # Platform-specific binary checks (not threshold-based)
    gpu = _get_gpu_info()
    if not gpu["assigned"]:
        warnings.append("NO GPU: No GPU assigned. You may have been throttled or GPU is unavailable.")
    if gpu["temperature_c"] is not None and gpu["temperature_c"] > 85:
        warnings.append(f"GPU HOT: Temperature at {gpu['temperature_c']}C. May cause thermal throttling.")

    drive = _get_drive_info()
    if not drive["mounted"]:
        warnings.append("DRIVE NOT MOUNTED: Cannot save checkpoints to Google Drive. Data will be lost on disconnect.")

    # Threshold-based warnings come from the central alert engine
    try:
        from bannin.intelligence.alerts import ThresholdEngine
        active = ThresholdEngine.get().get_active_alerts()
        for alert in active.get("active", []):
            warnings.append(alert["message"])
    except Exception:
        pass

    return warnings


def _format_duration(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
