_pynvml_available = False

try:
    import pynvml
    pynvml.nvmlInit()
    _pynvml_available = True
except Exception:
    pass


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
                name = name.decode("utf-8")

            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)

            try:
                temp = pynvml.nvmlDeviceGetTemperature(
                    handle, pynvml.NVML_TEMPERATURE_GPU
                )
            except Exception:
                temp = None

            gpus.append({
                "index": i,
                "name": name,
                "memory_total_mb": round(mem_info.total / (1024**2)),
                "memory_used_mb": round(mem_info.used / (1024**2)),
                "memory_free_mb": round(mem_info.free / (1024**2)),
                "memory_percent": round(mem_info.used / mem_info.total * 100, 1),
                "gpu_utilization_percent": util.gpu,
                "temperature_c": temp,
            })
    except Exception:
        pass

    return gpus
