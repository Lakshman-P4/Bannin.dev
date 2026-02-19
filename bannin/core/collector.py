import platform
import time
from datetime import datetime, timezone

import psutil


def get_cpu_metrics() -> dict:
    return {
        "percent": psutil.cpu_percent(interval=0.1),
        "per_core": psutil.cpu_percent(interval=0.1, percpu=True),
        "count_physical": psutil.cpu_count(logical=False),
        "count_logical": psutil.cpu_count(logical=True),
        "frequency_mhz": (
            psutil.cpu_freq().current if psutil.cpu_freq() else None
        ),
    }


def get_memory_metrics() -> dict:
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "percent": mem.percent,
    }


def get_disk_metrics(path: str = "/") -> dict:
    if platform.system() == "Windows":
        path = "C:\\"
    disk = psutil.disk_usage(path)
    return {
        "total_gb": round(disk.total / (1024**3), 2),
        "used_gb": round(disk.used / (1024**3), 2),
        "free_gb": round(disk.free / (1024**3), 2),
        "percent": disk.percent,
    }


def get_network_metrics() -> dict:
    net = psutil.net_io_counters()
    return {
        "bytes_sent": net.bytes_sent,
        "bytes_received": net.bytes_recv,
        "bytes_sent_mb": round(net.bytes_sent / (1024**2), 2),
        "bytes_received_mb": round(net.bytes_recv / (1024**2), 2),
    }


def get_all_metrics() -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "platform": platform.system(),
        "cpu": get_cpu_metrics(),
        "memory": get_memory_metrics(),
        "disk": get_disk_metrics(),
        "network": get_network_metrics(),
    }
