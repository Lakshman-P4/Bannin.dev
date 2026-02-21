import argparse
import json
import sys
import time


def main():
    parser = argparse.ArgumentParser(
        prog="bannin",
        description="Bannin -- universal monitoring agent",
    )
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start", help="Start the Bannin agent")
    start_parser.add_argument(
        "--port", type=int, default=8420, help="Port to run on (default: 8420)"
    )
    start_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )

    subparsers.add_parser("mcp", help="Start the Bannin MCP server (stdio)")

    analytics_parser = subparsers.add_parser("analytics", help="Start the analytics dashboard")
    analytics_parser.add_argument(
        "--port", type=int, default=8421, help="Port for analytics dashboard (default: 8421)"
    )
    analytics_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )

    history_parser = subparsers.add_parser("history", help="Query stored event history")
    history_parser.add_argument("--type", default="", help="Filter by event type")
    history_parser.add_argument("--severity", default="", help="Filter by severity (info, warning, critical)")
    history_parser.add_argument("--since", default="1h", help="How far back (e.g., 30m, 2h, 7d)")
    history_parser.add_argument("--search", default="", help="Full-text search query")
    history_parser.add_argument("--limit", type=int, default=50, help="Max events to show")
    history_parser.add_argument("--json", dest="output_json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if args.command == "start":
        _start_agent(host=args.host, port=args.port)
    elif args.command == "mcp":
        _start_mcp()
    elif args.command == "analytics":
        _start_analytics(host=args.host, port=args.port)
    elif args.command == "history":
        _query_history(args)
    else:
        parser.print_help()
        sys.exit(1)


def _start_agent(host: str, port: int):
    import uvicorn

    print()
    print(f"  Bannin agent v0.1.0")
    print(f"  Dashboard:  http://{host}:{port}")
    print(f"  API docs:   http://{host}:{port}/docs")
    print()

    uvicorn.run("bannin.api:app", host=host, port=port, log_level="warning")


def _start_mcp():
    try:
        from bannin.mcp.server import serve
        serve()
    except ImportError:
        print("Error: MCP SDK not installed. Install with: pip install bannin[mcp]")
        sys.exit(1)


def _start_analytics(host: str, port: int):
    import uvicorn

    print()
    print(f"  Bannin Analytics Dashboard")
    print(f"  Dashboard:  http://{host}:{port}")
    print()

    uvicorn.run("bannin.analytics.api:app", host=host, port=port, log_level="warning")


def _query_history(args):
    from bannin.analytics.store import AnalyticsStore
    store = AnalyticsStore.get()

    if args.search:
        events = store.search(args.search, limit=args.limit)
    else:
        since_ts = _parse_since(args.since)
        events = store.query(
            event_type=args.type or None,
            severity=args.severity or None,
            since=since_ts,
            limit=args.limit,
        )

    if args.output_json:
        print(json.dumps(events, indent=2, default=str))
        return

    if not events:
        print("No events found.")
        return

    print(f"  {len(events)} event(s) found\n")

    for e in events:
        ts = e.get("timestamp", "")
        if ts:
            # Trim to readable format
            ts = ts[:19].replace("T", " ")
        severity = e.get("severity", "")
        sev_marker = ""
        if severity == "critical":
            sev_marker = "[!!] "
        elif severity == "warning":
            sev_marker = "[!]  "
        elif severity == "info":
            sev_marker = "[i]  "
        else:
            sev_marker = "     "

        event_type = e.get("type", "unknown")
        message = e.get("message", "")

        print(f"  {ts}  {sev_marker}{event_type:20s}  {message}")


def _parse_since(since_str: str) -> float | None:
    s = since_str.strip().lower()
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    for suffix, mult in multipliers.items():
        if s.endswith(suffix):
            try:
                val = float(s[:-1])
                return time.time() - (val * mult)
            except ValueError:
                return None
    return None


if __name__ == "__main__":
    main()
