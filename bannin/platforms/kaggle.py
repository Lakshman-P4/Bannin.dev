import os
import time
import shutil
import socket

import psutil

from bannin.config.loader import get_kaggle_config

_session_start_time = time.time()


def _load_kaggle_limits():
    """Load Kaggle limits from remote config, falling back to defaults."""
    cfg = get_kaggle_config()

    session_cfg = cfg.get("session_limits_hours", {"cpu": 12, "gpu": 9, "tpu": 9})
    session_limits = {k: v * 3600 for k, v in session_cfg.items()}

    quotas = cfg.get("quotas", {})
    storage = cfg.get("storage", {})
    limits = cfg.get("limits", {})
    ram = cfg.get("ram_gb", {"cpu": 30, "gpu": 29, "tpu": 16})

    return {
        "session_limits": session_limits,
        "idle_timeout": cfg.get("idle_timeout_min", 60) * 60,
        "gpu_quota_hours": quotas.get("gpu_weekly_hours", 30),
        "tpu_quota_hours": quotas.get("tpu_weekly_hours", 20),
        "output_limit_gb": storage.get("output_limit_gb", 20),
        "output_file_limit": storage.get("output_file_limit", 500),
        "input_limit_gb": storage.get("input_limit_gb", 100),
        "notebook_source_limit_mb": storage.get("notebook_source_limit_mb", 1),
        "max_concurrent_gpu": limits.get("max_concurrent_gpu_sessions", 1),
        "dataset_limit_gb": limits.get("dataset_size_limit_gb", 100),
        "file_upload_web_mb": limits.get("file_upload_web_mb", 500),
        "file_upload_api_gb": limits.get("file_upload_api_gb", 2),
        "ram_limits": ram,
        "cpu_cores": cfg.get("cpu_cores", 4),
    }


_KL = _load_kaggle_limits()

SESSION_LIMITS = _KL["session_limits"]
IDLE_TIMEOUT = _KL["idle_timeout"]
WEEKLY_GPU_QUOTA_HOURS = _KL["gpu_quota_hours"]
WEEKLY_TPU_QUOTA_HOURS = _KL["tpu_quota_hours"]
OUTPUT_LIMIT_GB = _KL["output_limit_gb"]
OUTPUT_FILE_LIMIT = _KL["output_file_limit"]
INPUT_LIMIT_GB = _KL["input_limit_gb"]
NOTEBOOK_SOURCE_LIMIT_MB = _KL["notebook_source_limit_mb"]
FILE_UPLOAD_WEB_MB = _KL["file_upload_web_mb"]
FILE_UPLOAD_API_GB = _KL["file_upload_api_gb"]
DATASET_LIMIT_GB = _KL["dataset_limit_gb"]
RAM_LIMITS = _KL["ram_limits"]
CPU_CORES = _KL["cpu_cores"]

# GPU specs
GPU_SPECS = {
    "P100": {"vram_gb": 16, "memory_type": "HBM2", "bandwidth_gbps": 732, "cuda_cores": 3584, "tensor_cores": 0, "architecture": "Pascal"},
    "T4":   {"vram_gb": 16, "memory_type": "GDDR6", "bandwidth_gbps": 320, "cuda_cores": 2560, "tensor_cores": 320, "architecture": "Turing"},
}

# Concurrent session limits
MAX_CONCURRENT_GPU_SESSIONS = 1


def get_kaggle_metrics() -> dict:
    accel_type = _detect_accelerator_type()
    return {
        "platform": "kaggle",
        "session": _get_session_info(accel_type),
        "accelerator": _get_accelerator_info(accel_type),
        "ram": _get_ram_info(accel_type),
        "storage": _get_storage_info(),
        "internet": _check_internet_access(),
        "quota": _get_quota_info(accel_type),
        "limits": _get_hard_limits(accel_type),
        "warnings": _generate_warnings(accel_type),
    }


def _detect_accelerator_type() -> str:
    # Check for GPU
    try:
        import pynvml
        pynvml.nvmlInit()
        if pynvml.nvmlDeviceGetCount() > 0:
            return "gpu"
    except Exception:
        pass

    # Check for TPU
    if os.environ.get("TPU_NAME") or os.environ.get("TPU_WORKER_HOSTNAMES"):
        return "tpu"

    return "cpu"


def _get_session_info(accel_type: str) -> dict:
    elapsed = time.time() - _session_start_time
    max_session = SESSION_LIMITS.get(accel_type, SESSION_LIMITS["cpu"])
    remaining = max(0, max_session - elapsed)

    return {
        "accelerator_mode": accel_type,
        "elapsed_seconds": round(elapsed),
        "elapsed_human": _format_duration(elapsed),
        "max_session_seconds": max_session,
        "max_session_human": _format_duration(max_session),
        "remaining_seconds": round(remaining),
        "remaining_human": _format_duration(remaining),
        "percent_used": round((elapsed / max_session) * 100, 1),
        "idle_timeout_seconds": IDLE_TIMEOUT,
        "idle_timeout_human": _format_duration(IDLE_TIMEOUT),
        "idle_note": "Kaggle shows 'Are you still there?' prompts. 60 min inactivity = disconnect.",
    }


def _get_accelerator_info(accel_type: str) -> dict:
    result = {
        "type": accel_type,
        "name": None,
        "gpu_count": 0,
        "memory_total_gb": None,
        "memory_used_gb": None,
        "memory_free_gb": None,
        "memory_percent": None,
        "utilization_percent": None,
        "temperature_c": None,
        "power_watts": None,
        "specs": None,
    }

    if accel_type == "gpu":
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            result["gpu_count"] = device_count

            # Report on first GPU (primary)
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            result["name"] = name

            # Aggregate memory across all GPUs
            total_mem = 0
            used_mem = 0
            for i in range(device_count):
                h = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                total_mem += mem.total
                used_mem += mem.used

            result["memory_total_gb"] = round(total_mem / (1024**3), 2)
            result["memory_used_gb"] = round(used_mem / (1024**3), 2)
            result["memory_free_gb"] = round((total_mem - used_mem) / (1024**3), 2)
            result["memory_percent"] = round(used_mem / total_mem * 100, 1) if total_mem > 0 else 0

            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            result["utilization_percent"] = util.gpu

            try:
                result["temperature_c"] = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            except Exception:
                pass

            try:
                result["power_watts"] = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000, 1)
            except Exception:
                pass

            # Match known specs
            for key, specs in GPU_SPECS.items():
                if key.lower() in name.lower():
                    result["specs"] = specs
                    break

            # Special note for dual T4
            if device_count == 2 and "T4" in name:
                result["name"] = f"{name} x2 (dual GPU)"

        except Exception:
            pass

    elif accel_type == "tpu":
        tpu_name = os.environ.get("TPU_NAME", "TPU")
        result["name"] = tpu_name
        result["memory_total_gb"] = 128  # 8 cores x 16 GB HBM each
        result["specs"] = {
            "type": "TPU v3-8 or v5e-8",
            "cores": 8,
            "hbm_per_core_gb": 16,
            "total_hbm_gb": 128,
            "note": "Kaggle is transitioning from TPU v3-8 to TPU v5e-8.",
        }

    return result


def _get_ram_info(accel_type: str) -> dict:
    mem = psutil.virtual_memory()
    expected_limit = RAM_LIMITS.get(accel_type, RAM_LIMITS["cpu"])
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "percent": mem.percent,
        "expected_limit_gb": expected_limit,
        "cpu_cores": CPU_CORES,
        "swap_total_gb": round(psutil.swap_memory().total / (1024**3), 2),
        "swap_used_gb": round(psutil.swap_memory().used / (1024**3), 2),
        "note": "If RAM is exceeded, the notebook is killed and restarted. All state is lost.",
    }


def _get_storage_info() -> dict:
    working_dir = "/kaggle/working"
    input_dir = "/kaggle/input"

    result = {
        "disk": {
            "total_gb": None,
            "used_gb": None,
            "free_gb": None,
            "percent": None,
            "note": "Kaggle uses a shared filesystem. Focus on the 20 GB output limit, not total disk.",
        },
        "output": {
            "dir": working_dir,
            "limit_gb": OUTPUT_LIMIT_GB,
            "file_limit": OUTPUT_FILE_LIMIT,
            "used_gb": None,
            "file_count": None,
            "ephemeral": True,
            "note": "Only saved if you commit. Files in /tmp are always lost.",
        },
        "input": {
            "dir": input_dir,
            "limit_gb": INPUT_LIMIT_GB,
            "used_gb": None,
            "read_only": True,
        },
    }

    # Disk usage
    try:
        usage = shutil.disk_usage("/")
        result["disk"]["used_gb"] = round(usage.used / (1024**3), 2)
        result["disk"]["free_gb"] = round(usage.free / (1024**3), 2)
        result["disk"]["percent"] = round(usage.used / usage.total * 100, 1)
    except Exception:
        pass

    # Output directory size and file count
    try:
        total_size = 0
        file_count = 0
        for dirpath, dirnames, filenames in os.walk(working_dir):
            for f in filenames:
                file_count += 1
                try:
                    total_size += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
        result["output"]["used_gb"] = round(total_size / (1024**3), 2)
        result["output"]["file_count"] = file_count
    except Exception:
        pass

    # Input directory size
    try:
        total_input = 0
        for dirpath, dirnames, filenames in os.walk(input_dir):
            for f in filenames:
                try:
                    total_input += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
        result["input"]["used_gb"] = round(total_input / (1024**3), 2)
    except Exception:
        pass

    return result


def _check_internet_access() -> dict:
    has_internet = False
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        has_internet = True
    except (socket.timeout, OSError):
        pass

    return {
        "available": has_internet,
        "note": (
            None if has_internet
            else "Internet is disabled (likely a competition notebook). Cannot pip install or download data. Pre-load packages and models as Kaggle datasets."
        ),
    }


def _get_quota_info(accel_type: str) -> dict:
    elapsed = time.time() - _session_start_time
    gpu_hours_this_session = round(elapsed / 3600, 2) if accel_type == "gpu" else 0
    tpu_hours_this_session = round(elapsed / 3600, 2) if accel_type == "tpu" else 0

    return {
        "gpu": {
            "weekly_limit_hours": WEEKLY_GPU_QUOTA_HOURS,
            "this_session_hours": gpu_hours_this_session,
            "quota_type": "rolling 7-day window",
            "note": "Check kaggle.com/me/account for remaining quota. Usage from 7 days ago rolls off.",
        },
        "tpu": {
            "weekly_limit_hours": WEEKLY_TPU_QUOTA_HOURS,
            "this_session_hours": tpu_hours_this_session,
            "quota_type": "rolling 7-day window",
            "note": "TPU quota is separate from GPU quota.",
        },
    }


def _get_hard_limits(accel_type: str) -> dict:
    return {
        "notebook_source_limit_mb": NOTEBOOK_SOURCE_LIMIT_MB,
        "output_file_limit": OUTPUT_FILE_LIMIT,
        "output_size_limit_gb": OUTPUT_LIMIT_GB,
        "input_data_limit_gb": INPUT_LIMIT_GB,
        "dataset_size_limit_gb": DATASET_LIMIT_GB,
        "file_upload_web_mb": FILE_UPLOAD_WEB_MB,
        "file_upload_api_gb": FILE_UPLOAD_API_GB,
        "max_concurrent_gpu_sessions": MAX_CONCURRENT_GPU_SESSIONS,
        "phone_verification_required": True,
        "persistence_available": True,
        "note": "Persistence mode saves /kaggle/working files between sessions but adds overhead.",
    }


def _generate_warnings(accel_type: str) -> list[str]:
    warnings = []

    # Platform-specific binary checks (not threshold-based)
    if accel_type == "cpu":
        warnings.append("NO ACCELERATOR: Running on CPU only. Enable GPU/TPU in notebook settings if needed.")

    accel = _get_accelerator_info(accel_type)
    if accel["temperature_c"] is not None and accel["temperature_c"] > 85:
        warnings.append(f"GPU HOT: Temperature at {accel['temperature_c']}C. May cause thermal throttling.")

    # Kaggle-specific: output file count (not a simple percent threshold)
    storage = _get_storage_info()
    output = storage["output"]
    if output["file_count"] is not None and output["file_count"] > 400:
        warnings.append(f"OUTPUT FILES HIGH: {output['file_count']} of {OUTPUT_FILE_LIMIT} file limit. Consider zipping files.")

    # Internet check
    internet = _check_internet_access()
    if not internet["available"]:
        warnings.append("NO INTERNET: External downloads and pip installs will fail. Use pre-loaded datasets.")

    # GPU quota reminder (informational, not a threshold alert)
    if accel_type == "gpu":
        quota = _get_quota_info(accel_type)
        if quota["gpu"]["this_session_hours"] > 2:
            remaining_quota_estimate = WEEKLY_GPU_QUOTA_HOURS - quota["gpu"]["this_session_hours"]
            warnings.append(f"GPU QUOTA: Used {quota['gpu']['this_session_hours']}h this session. ~{round(remaining_quota_estimate, 1)}h may remain this week (check kaggle.com/me/account).")

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
