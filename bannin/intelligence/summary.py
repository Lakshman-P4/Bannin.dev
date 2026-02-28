"""Plain-English system summary generator.

Produces a human-readable summary of system health with four levels:
healthy, busy, strained, critical. Includes suggestions when stressed.
No LLM calls — purely rule-based.
"""

from __future__ import annotations

from bannin.core.collector import get_cpu_metrics, get_memory_metrics, get_disk_metrics
from bannin.core.process import get_resource_breakdown
from bannin.log import logger


def generate_summary() -> dict:
    """Generate a plain-English system health summary.

    Returns:
        {
            "level": "healthy" | "busy" | "strained" | "critical",
            "headline": "Your computer is running smoothly.",
            "details": "Everything looks healthy right now.",
            "suggestions": ["Close some Chrome tabs to free up memory."],
        }
    """
    try:
        cpu = get_cpu_metrics()
        mem = get_memory_metrics()
        disk = get_disk_metrics()
        breakdown = get_resource_breakdown()
    except Exception:
        logger.warning("Failed to collect metrics for summary", exc_info=True)
        return {
            "level": "healthy",
            "headline": "Unable to collect system metrics right now.",
            "details": "Metric collection encountered an error. This is usually temporary.",
            "suggestions": [],
        }

    cpu_pct = cpu.get("percent", 0)
    ram_pct = mem.get("percent", 0)
    ram_used = mem.get("used_gb", 0)
    ram_total = mem.get("total_gb", 0)
    disk_pct = disk.get("percent", 0)

    # Determine overall level based on worst metric
    level = _calculate_level(cpu_pct, ram_pct, disk_pct)

    headline = _HEADLINES[level]
    details = _build_details(level, cpu_pct, ram_pct, ram_used, ram_total, disk_pct, breakdown)
    suggestions = _build_suggestions(cpu_pct, ram_pct, disk_pct, breakdown)

    return {
        "level": level,
        "headline": headline,
        "details": details,
        "suggestions": suggestions,
    }


_HEADLINES = {
    "healthy": "Your computer is running smoothly.",
    "busy": "Your computer is a little busy right now.",
    "strained": "Your computer is under heavy load.",
    "critical": "Your computer is critically strained.",
}


def _calculate_level(cpu_pct: float, ram_pct: float, disk_pct: float) -> str:
    """Determine health level from the worst metric."""
    worst = max(cpu_pct, ram_pct)

    if worst >= 95 or ram_pct >= 95:
        return "critical"
    if worst >= 80 or disk_pct >= 95:
        return "strained"
    if worst >= 60:
        return "busy"
    return "healthy"


def _build_details(
    level: str,
    cpu_pct: float,
    ram_pct: float,
    ram_used: float,
    ram_total: float,
    disk_pct: float,
    breakdown: dict,
) -> str:
    """Build the detail text explaining what's happening."""
    if level == "healthy":
        return "Everything looks good. CPU, memory, and disk are all at comfortable levels."

    parts = []

    # Mention the stressed resources
    if ram_pct >= 80:
        parts.append(
            f"RAM is at {ram_pct:.0f}% ({ram_used:.1f} GB of {ram_total:.1f} GB)"
        )
    if cpu_pct >= 80:
        parts.append(f"CPU is at {cpu_pct:.0f}%")
    if disk_pct >= 90:
        parts.append(f"Disk is at {disk_pct:.0f}%")

    if not parts:
        # Moderate load
        if ram_pct >= 60:
            parts.append(f"RAM is at {ram_pct:.0f}%")
        if cpu_pct >= 60:
            parts.append(f"CPU is at {cpu_pct:.0f}%")

    detail = ". ".join(parts) + "." if parts else ""

    # Add top consumers
    top_ram = breakdown.get("ram", [])
    if top_ram and ram_pct >= 60:
        names = [f"{r['name']} ({r['display']})" for r in top_ram[:3]]
        detail += " The biggest memory users are " + ", ".join(names) + "."

    top_cpu = breakdown.get("cpu", [])
    if top_cpu and cpu_pct >= 60:
        names = [f"{c['name']} ({c['display']})" for c in top_cpu[:3]]
        detail += " Top CPU consumers: " + ", ".join(names) + "."

    return detail


def _build_suggestions(
    cpu_pct: float,
    ram_pct: float,
    disk_pct: float,
    breakdown: dict,
) -> list[str]:
    """Generate actionable suggestions based on current state."""
    suggestions = []

    if ram_pct < 60 and cpu_pct < 60 and disk_pct < 90:
        return suggestions

    top_ram = breakdown.get("ram", [])

    # Check if browsers are heavy RAM consumers
    browser_names = {"Google Chrome", "Microsoft Edge", "Mozilla Firefox", "Safari",
                     "Brave Browser", "Opera", "Vivaldi", "Arc Browser"}
    if ram_pct >= 70:
        for r in top_ram[:3]:
            if r["name"] in browser_names:
                suggestions.append(
                    f"Consider closing some {r['name']} tabs to free up memory."
                )
                break

    if ram_pct >= 85:
        non_browser = [r for r in top_ram if r["name"] not in browser_names]
        if non_browser:
            suggestions.append(
                f"You could close {non_browser[0]['name']} if you're not actively using it."
            )

    if cpu_pct >= 80:
        top_cpu = breakdown.get("cpu", [])
        if top_cpu and top_cpu[0]["value"] > 30:
            suggestions.append(
                f"{top_cpu[0]['name']} is using a lot of CPU ({top_cpu[0]['display']})."
            )

    if disk_pct >= 90:
        suggestions.append("Disk space is getting low. Consider freeing up some space.")

    if disk_pct >= 95:
        suggestions.append("Disk is almost full — this can slow down your computer significantly.")

    return suggestions
