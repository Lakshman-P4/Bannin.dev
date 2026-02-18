import platform
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vigilo.core.collector import get_all_metrics
from vigilo.core.gpu import get_gpu_metrics, is_gpu_available
from vigilo.core.process import get_process_count, get_top_processes
from vigilo.platforms.detector import detect_platform

_start_time = time.time()
_detected_platform = detect_platform()

app = FastAPI(
    title="Vigilo Agent",
    description="Universal monitoring agent -- system metrics, GPU, processes, cloud notebooks",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    return {
        "agent": "vigilo",
        "version": "0.1.0",
        "hostname": platform.node(),
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": platform.python_version(),
        "gpu_available": is_gpu_available(),
        "environment": _detected_platform,
        "uptime_seconds": round(time.time() - _start_time, 1),
    }


@app.get("/metrics")
def metrics():
    data = get_all_metrics()
    data["gpu"] = get_gpu_metrics()
    data["environment"] = _detected_platform
    return data


@app.get("/processes")
def processes(limit: int = 10):
    return {
        "summary": get_process_count(),
        "top_processes": get_top_processes(limit=limit),
    }


@app.get("/platform")
def platform_info():
    """Platform-specific monitoring for Colab, Kaggle, or local."""
    if _detected_platform == "colab":
        from vigilo.platforms.colab import get_colab_metrics
        return get_colab_metrics()
    elif _detected_platform == "kaggle":
        from vigilo.platforms.kaggle import get_kaggle_metrics
        return get_kaggle_metrics()
    else:
        return {
            "platform": "local",
            "message": "Running on a local machine. Colab/Kaggle-specific monitoring is not applicable.",
        }


@app.get("/llm/usage")
def llm_usage():
    """LLM token and cost tracking summary."""
    from vigilo.llm.tracker import LLMTracker
    tracker = LLMTracker.get()
    return tracker.get_summary()


@app.get("/llm/calls")
def llm_calls(limit: int = 20):
    """Recent LLM API calls."""
    from vigilo.llm.tracker import LLMTracker
    tracker = LLMTracker.get()
    return {"calls": tracker.get_calls(limit=limit)}


@app.get("/llm/context")
def llm_context(model: str = "", tokens: int = 0):
    """Context window usage prediction for a model."""
    from vigilo.llm.tracker import LLMTracker
    tracker = LLMTracker.get()
    if not model:
        return {"error": "Provide ?model=gpt-4o&tokens=50000"}
    return tracker.get_context_usage(model, tokens)


@app.get("/llm/latency")
def llm_latency(model: str = ""):
    """Latency trend analysis."""
    from vigilo.llm.tracker import LLMTracker
    tracker = LLMTracker.get()
    return tracker.get_latency_trend(model=model or None)


@app.get("/tasks")
def tasks():
    return {
        "active_tasks": [],
        "message": "Task tracking coming soon -- will monitor long-running processes, training runs, and notebook sessions.",
    }
