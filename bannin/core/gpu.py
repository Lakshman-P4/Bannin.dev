from __future__ import annotations

from bannin.log import logger

_pynvml_available = False

try:
    import pynvml
    pynvml.nvmlInit()
    _pynvml_available = True
except Exception:
    logger.debug("NVIDIA GPU monitoring unavailable (pynvml not installed or no GPU)")


def is_gpu_available() -> bool:
    return _pynvml_available


def get_gpu_metrics() -> list[dict]:
    if not _pynvml_available:
        return []

    gpus = []
    try:
        device_count = pynvml.nvmlDeviceGetCount()
        for i in range(device_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                try:
                    name = name.decode("utf-8")
                except UnicodeDecodeError:
                    name = name.decode("utf-8", errors="replace")

            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)

            try:
                temp = pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU
                )
            except Exception:
                logger.debug("GPU temperature read failed for device %d", i)
                temp = None

            mem_percent = (
                round(mem_info.used / mem_info.total * 100, 1)
                if mem_info.total > 0
                else 0.0
            )

            gpus.append({
                "index": i,
                "name": name,
                "memory_total_mb": round(mem_info.total / (1024**2)),
                "memory_used_mb": round(mem_info.used / (1024**2)),
                "memory_free_mb": round(mem_info.free / (1024**2)),
                "memory_percent": mem_percent,
                "gpu_utilization_percent": util.gpu,
                "temperature_c": temp,
            })
    except Exception:
        logger.warning("GPU metrics collection failed", exc_info=True)

    return gpus
