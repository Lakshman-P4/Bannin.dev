"""L2 recommendation engine -- actionable suggestions from cross-signal analysis.

Pure-function module: takes a full metrics snapshot (system + LLM + Ollama +
MCP session + platform) and produces prioritized, human-readable recommendations.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bannin.log import logger


def generate_recommendations(snapshot: dict) -> list[dict]:
    """Generate prioritized recommendations from a unified metrics snapshot.

    Args:
        snapshot: Dict with keys like system, llm, ollama, mcp, platform,
                  predictions, processes, health, alerts.

    Returns:
        List of recommendation dicts, sorted by priority (1 = most critical).
    """
    recs = []
    _id = 0

    def add(priority: int, category: str, message: str, action: str, confidence: float = 0.8) -> None:
        nonlocal _id
        _id += 1
        recs.append({
            "id": f"rec_{_id}",
            "priority": priority,
            "category": category,
            "message": message,
            "action": action,
            "confidence": round(confidence, 2),
        })

    # --- Rule 1: OOM imminent ---
    oom = snapshot.get("predictions", {}).get("oom", {})
    ram_oom = oom.get("ram", {})
    if ram_oom.get("confidence", 0) >= 70 and ram_oom.get("minutes_until_full", 999) <= 10:
        mins = ram_oom.get("minutes_until_full", 0)
        add(1, "system", f"OOM predicted in ~{mins:.0f} minutes",
            "Reduce batch size, checkpoint your work, or close memory-heavy apps", 0.9)

    # --- Rule 2: Session expiring (Colab/Kaggle) ---
    platform_data = snapshot.get("platform", {})
    session = platform_data.get("session", {})
    remaining = session.get("remaining_seconds")
    if remaining is not None and remaining <= 900:
        mins = remaining / 60
        add(1, "platform", f"Session expires in ~{mins:.0f} minutes",
            "Save your work and checkpoint model weights now", 0.95)

    # --- Rule 3: Conversation health degraded ---
    health = snapshot.get("health", {})
    health_score = health.get("health_score")
    if health_score is not None and health_score <= 40:
        rating = health.get("rating", "poor")
        add(2, "llm", f"Conversation health is {rating} ({health_score}/100)",
            health.get("recommendation", "Start a new conversation"), 0.85)

    # --- Rule 4: Context window filling ---
    danger_zone = health.get("danger_zone") or {}
    if danger_zone.get("in_danger_zone"):
        dz_pct = danger_zone.get("danger_zone_percent", 80)
        model = danger_zone.get("model", "current model")
        components = health.get("components", {})
        ctx = components.get("context_freshness", {})
        ctx_detail = ctx.get("detail", "")
        add(2, "llm", f"Context past {dz_pct}% danger zone for {model}",
            f"Quality degrades beyond this point. {ctx_detail}", 0.85)

    # --- Rule 5: MCP session fatigue ---
    mcp = snapshot.get("mcp", {})
    mcp_fatigue = mcp.get("session_fatigue", 0)
    if mcp_fatigue >= 60:
        tool_calls = mcp.get("total_tool_calls", 0)
        add(3, "llm", f"MCP session fatigue high ({mcp_fatigue:.0f}/100) after {tool_calls} tool calls",
            "Context quality is degrading. Summarize progress and start a fresh session.", 0.8)

    # --- Rule 6: RAM pressure with cause ---
    memory = snapshot.get("memory", {})
    ram_pct = memory.get("percent", 0)
    if ram_pct >= 80:
        top_procs = snapshot.get("top_processes", [])
        # Find the biggest process that's actually worth closing (>= 200 MB)
        culprit = None
        for proc in (top_procs or []):
            mem_mb = proc.get("memory_mb", 0)
            if mem_mb >= 200:
                culprit = proc
                break
        if culprit:
            name = culprit.get("name", "Unknown")
            mem_gb = culprit.get("memory_mb", 0) / 1024
            add(3, "system", f"RAM at {ram_pct:.0f}% -- {name} using {mem_gb:.1f} GB",
                f"Close {name} if not actively needed to free memory", 0.85)
        else:
            add(3, "system", f"RAM at {ram_pct:.0f}%",
                "Close unused applications to free memory", 0.75)

    # --- Rule 7: Ollama VRAM pressure ---
    ollama = snapshot.get("ollama", {})
    vram_pressure = ollama.get("vram_pressure", 0)
    if vram_pressure >= 75:
        models = ollama.get("models", [])
        model_names = ", ".join(m.get("name", "") for m in models[:3]) if models else "loaded model"
        add(3, "local_llm", f"Ollama VRAM at {vram_pressure:.0f}% ({model_names})",
            "Consider unloading unused models or closing GPU-intensive apps", 0.8)

    # --- Rule 8: CPU saturated ---
    cpu = snapshot.get("cpu", {})
    cpu_pct = cpu.get("percent", 0)
    if cpu_pct >= 90:
        top_procs = snapshot.get("top_processes", [])
        if top_procs:
            top = top_procs[0]
            add(4, "system", f"CPU at {cpu_pct:.0f}% -- {top.get('name', '')} is the top consumer",
                f"Close {top.get('name', 'the heaviest process')} or wait for it to finish", 0.8)
        else:
            add(4, "system", f"CPU saturated at {cpu_pct:.0f}%",
                "Check running processes and close unnecessary apps", 0.7)

    # --- Rule 9: Disk critically low ---
    disk = snapshot.get("disk", {})
    disk_free = disk.get("free_gb", 999)
    disk_pct = disk.get("percent", 0)
    if disk_pct >= 90 or disk_free <= 5:
        add(4, "system", f"Disk at {disk_pct:.0f}% with {disk_free:.1f} GB free",
            "Clear temp files, old downloads, or run Disk Cleanup", 0.9)

    # --- Rule 10: LLM cost trending up ---
    llm = snapshot.get("llm", {})
    total_cost = llm.get("total_cost_usd", 0)
    if total_cost >= 5.0:
        add(5, "llm", f"Session LLM spend: ${total_cost:.2f}",
            "Consider using a cheaper model for routine tasks", 0.7)

    # --- Rule 11: Latency degrading ---
    if health_score is not None:
        latency_comp = health.get("components", {}).get("latency_health", {})
        latency_score = latency_comp.get("score", 100)
        if latency_score <= 50:
            add(5, "llm", f"Response latency degrading: {latency_comp.get('detail', '')}",
                "Check if your machine is under load or if the provider is slow", 0.7)

    # --- Rule 12: Ollama model about to unload ---
    for model_info in ollama.get("models", [])[:50]:
        expires = model_info.get("expires_at", "")
        if expires:
            try:
                # Ollama returns ISO format expiry
                exp_dt = datetime.fromisoformat(expires.replace("Z", "+00:00"))
                remaining_sec = (exp_dt - datetime.now(timezone.utc)).total_seconds()
                if 0 < remaining_sec < 300:
                    add(5, "local_llm", f"Model '{model_info.get('name', '')}' expires in {remaining_sec / 60:.0f} minutes",
                        "Send a request to keep the model loaded, or it will auto-unload", 0.75)
            except (ValueError, TypeError):
                logger.debug("Failed to parse Ollama model expiry timestamp")

    # Sort by priority
    recs.sort(key=lambda r: r["priority"])
    return recs


def build_recommendation_snapshot() -> dict:
    """Build a full snapshot from all available sources and generate recommendations."""
    snapshot = {}

    # System metrics
    try:
        from bannin.core.collector import get_cpu_metrics, get_memory_metrics, get_disk_metrics
        snapshot["cpu"] = get_cpu_metrics()
        snapshot["memory"] = get_memory_metrics()
        snapshot["disk"] = get_disk_metrics()
    except Exception:
        logger.debug("System metrics unavailable for recommendations")

    # Top processes
    try:
        from bannin.core.process import get_grouped_processes
        snapshot["top_processes"] = get_grouped_processes(limit=5)
    except Exception:
        logger.debug("Process data unavailable for recommendations")

    # OOM predictions
    try:
        from bannin.intelligence.oom import OOMPredictor
        snapshot["predictions"] = {"oom": OOMPredictor.get().predict()}
    except Exception:
        logger.debug("OOM predictions unavailable for recommendations")

    # LLM health
    try:
        from bannin.llm.tracker import LLMTracker
        tracker = LLMTracker.get()
        summary = tracker.get_summary()
        snapshot["llm"] = summary

        # Get health with all available signals
        session_fatigue = None
        vram_pressure = None

        try:
            from bannin.state import get_mcp_session_data
            mcp_data = get_mcp_session_data()
            if mcp_data:
                snapshot["mcp"] = mcp_data
                session_fatigue = mcp_data
        except Exception:
            logger.debug("MCP session data unavailable for recommendations")

        try:
            from bannin.llm.ollama import OllamaMonitor
            ollama_health = OllamaMonitor.get().get_health()
            snapshot["ollama"] = ollama_health
            if ollama_health.get("available"):
                vram_pressure = ollama_health.get("vram_pressure")
        except Exception:
            logger.debug("Ollama health unavailable for recommendations")

        health = tracker.get_health(
            session_fatigue=session_fatigue,
            vram_pressure=vram_pressure,
        )
        snapshot["health"] = health
    except Exception:
        logger.debug("LLM health unavailable for recommendations")

    # Platform
    try:
        from bannin.platforms.detector import detect_platform
        plat = detect_platform()
        if plat == "colab":
            from bannin.platforms.colab import get_colab_metrics
            snapshot["platform"] = get_colab_metrics()
        elif plat == "kaggle":
            from bannin.platforms.kaggle import get_kaggle_metrics
            snapshot["platform"] = get_kaggle_metrics()
    except Exception:
        logger.debug("Platform metrics unavailable for recommendations")

    return snapshot
