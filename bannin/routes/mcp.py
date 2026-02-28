"""MCP session and Ollama endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict

from bannin.log import logger
from bannin.state import get_mcp_sessions, store_mcp_session

router = APIRouter(tags=["mcp"])


class MCPSessionPush(BaseModel):
    """Validated schema for MCP session health pushes."""
    model_config = ConfigDict(extra="allow")

    session_id: str = Field(default="_legacy", max_length=128)
    client_label: str = Field(default="Unknown", max_length=256)
    session_fatigue: float = Field(default=0, ge=0, le=100)
    tool_call_burden: float = Field(default=0, ge=0, le=100)
    estimated_context_percent: float = Field(default=0, ge=0, le=100)
    session_duration_minutes: float = Field(default=0, ge=0, le=525600)
    total_tool_calls: int = Field(default=0, ge=0, le=1000000)
    context_pressure: float = Field(default=0, ge=0, le=100)
    data_source: str = Field(default="estimated", max_length=64)


@router.post("/mcp/session")
def mcp_session_update(body: MCPSessionPush) -> dict:
    """Receive MCP session health data pushed from an MCP server process."""
    data = body.model_dump()
    session_id = data.get("session_id") or "_legacy"
    store_mcp_session(session_id, data)
    try:
        from bannin.analytics.pipeline import EventPipeline
        EventPipeline.get().emit({
            "type": "mcp_session_push",
            "source": "mcp",
            "severity": "info",
            "message": f"MCP session update: {data.get('client_label', 'Unknown')}",
            "data": {"session_id": session_id, "fatigue": data.get("session_fatigue", 0)},
        })
    except Exception:
        logger.debug("Failed to emit mcp_session_push event", exc_info=True)
    return {"status": "ok"}


@router.get("/mcp/sessions")
def mcp_sessions_list() -> dict:
    """All live MCP sessions with their health data."""
    sessions = get_mcp_sessions()
    return {
        "sessions": list(sessions.values()),
        "count": len(sessions),
    }


@router.get("/ollama")
def ollama_status() -> dict:
    """Ollama local LLM status -- loaded models, VRAM, availability."""
    from bannin.llm.ollama import OllamaMonitor
    return OllamaMonitor.get().get_health()
