"""Intelligence endpoints -- predictions, history, alerts, tasks, summary, recommendations, chat."""

from __future__ import annotations

from fastapi import APIRouter, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from bannin.log import logger
from bannin.routes import error_response

router = APIRouter(tags=["intelligence"])


class ChatMessage(BaseModel):
    """Validated schema for chatbot messages."""
    message: str = Field(default="", max_length=10000)


class TaskProgressUpdate(BaseModel):
    """Validated schema for external task progress reports."""
    name: str = Field(..., min_length=1, max_length=256)
    current: int = Field(..., ge=0)
    total: int | None = Field(default=None, ge=1)
    pid: int | None = Field(default=None, ge=1)


@router.get("/predictions/oom")
def predictions_oom() -> dict:
    """Predict out-of-memory events based on memory usage trends."""
    from bannin.intelligence.oom import OOMPredictor
    return OOMPredictor.get().predict()


@router.get("/history/memory")
def history_memory(minutes: float = Query(default=5, ge=0.5, le=60)) -> dict:
    """Memory usage history over the last N minutes (for graphing)."""
    from bannin.intelligence.history import MetricHistory
    history = MetricHistory.get()
    readings = history.get_memory_history(last_n_minutes=minutes)
    return {
        "readings": readings,
        "count": len(readings),
        "period_minutes": minutes,
        "total_readings_stored": history.reading_count,
    }


@router.get("/alerts")
def alerts(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    """Full alert history for this session."""
    from bannin.intelligence.alerts import ThresholdEngine
    return ThresholdEngine.get().get_alerts(limit=limit)


@router.get("/alerts/active")
def alerts_active() -> dict:
    """Currently active alerts (fired within their cooldown window)."""
    from bannin.intelligence.alerts import ThresholdEngine
    return ThresholdEngine.get().get_active_alerts()


@router.get("/tasks")
def tasks() -> dict:
    """Tracked tasks -- training progress and ETAs."""
    from bannin.intelligence.progress import ProgressTracker
    return ProgressTracker.get().get_tasks()


@router.post("/tasks")
def update_task_progress(body: TaskProgressUpdate) -> dict:
    """Register or update an external training task.

    External scripts call this via bannin.progress() to push progress
    to the running agent without needing bannin.watch().
    """
    from bannin.intelligence.progress import ProgressTracker
    return ProgressTracker.get().upsert_external(
        name=body.name,
        current=body.current,
        total=body.total,
        pid=body.pid,
    )


@router.post("/tasks/detected/{pid}/dismiss", response_model=None)
def dismiss_detected_task(pid: int = Path(ge=1)) -> dict | JSONResponse:
    """Dismiss a detected training process from the UI."""
    from bannin.intelligence.training import TrainingDetector
    detector = TrainingDetector.get()
    detector.mark_finished(pid)
    return {"status": "ok", "pid": pid}


@router.get("/tasks/{task_id}", response_model=None)
def task_detail(task_id: str = Path(max_length=256)) -> dict | JSONResponse:
    """Get details of a single tracked task."""
    from bannin.intelligence.progress import ProgressTracker
    task = ProgressTracker.get().get_task(task_id)
    if task is None:
        return error_response(404, "Task not found", f"Task '{task_id}' does not exist")
    return task


@router.get("/summary")
def summary() -> dict:
    """Plain-English system health summary for non-technical users."""
    from bannin.intelligence.summary import generate_summary
    return generate_summary()


@router.get("/recommendations")
def recommendations() -> dict:
    """L2 actionable recommendations from cross-signal analysis."""
    from bannin.intelligence.recommendations import build_recommendation_snapshot, generate_recommendations
    snapshot = build_recommendation_snapshot()
    return {"recommendations": generate_recommendations(snapshot)}


@router.post("/chat")
def chat_endpoint(body: ChatMessage) -> dict:
    """Chatbot endpoint -- natural language system health assistant."""
    from bannin.intelligence.chat import chat
    if not body.message.strip():
        return chat("")
    result = chat(body.message)
    try:
        from bannin.analytics.pipeline import EventPipeline
        EventPipeline.get().emit({
            "type": "chat_message",
            "source": "agent",
            "severity": "info",
            "message": f"Chat intent: {result.get('intent', 'unknown')}",
            "data": {"intent": result.get("intent", "unknown")},
        })
    except Exception:
        logger.debug("Failed to emit chat_message event", exc_info=True)
    return result
