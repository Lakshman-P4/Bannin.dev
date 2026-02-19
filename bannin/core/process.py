import psutil


def get_top_processes(limit: int = 10) -> list[dict]:
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status", "create_time"]):
        try:
            info = proc.info
            if info["cpu_percent"] is None:
                continue
            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": round(info["cpu_percent"], 1),
                "memory_percent": round(info["memory_percent"], 1),
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda p: p["cpu_percent"], reverse=True)
    return processes[:limit]


def get_process_count() -> dict:
    total = 0
    running = 0
    sleeping = 0

    for proc in psutil.process_iter(["status"]):
        try:
            total += 1
            status = proc.info["status"]
            if status == psutil.STATUS_RUNNING:
                running += 1
            elif status == psutil.STATUS_SLEEPING:
                sleeping += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "total": total,
        "running": running,
        "sleeping": sleeping,
    }
