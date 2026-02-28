from __future__ import annotations

import argparse
import json
import math
import sys
import time



def _valid_port(value: str) -> int:
    """Validate port is an integer in range 1-65535."""
    port = int(value)
    if port < 1 or port > 65535:
        raise argparse.ArgumentTypeError(f"port must be 1-65535, got {port}")
    return port


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bannin",
        description="Bannin -- universal monitoring agent",
    )
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start", help="Start the Bannin agent")
    start_parser.add_argument(
        "--port", type=_valid_port, default=8420, help="Port to run on (default: 8420)"
    )
    start_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    start_parser.add_argument(
        "--relay-key", default="", help="Agent API key for relay server connection"
    )
    start_parser.add_argument(
        "--relay-url", default="ws://localhost:3001",
        help="Relay server URL (default: ws://localhost:3001)"
    )

    stop_parser = subparsers.add_parser("stop", help="Stop the running Bannin agent")
    stop_parser.add_argument(
        "--port", type=_valid_port, default=8420, help="Port the agent is running on (default: 8420)"
    )

    subparsers.add_parser("mcp", help="Start the Bannin MCP server (stdio)")

    analytics_parser = subparsers.add_parser("analytics", help="Start the analytics dashboard")
    analytics_parser.add_argument(
        "--port", type=_valid_port, default=8421, help="Port for analytics dashboard (default: 8421)"
    )
    analytics_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )

    history_parser = subparsers.add_parser("history", help="Query stored event history")
    history_parser.add_argument("--type", default="", help="Filter by event type")
    history_parser.add_argument("--severity", default="", help="Filter by severity (info, warning, critical)")
    history_parser.add_argument("--since", default="1h", help="How far back (e.g., 30m, 2h, 7d)")
    history_parser.add_argument("--search", default="", help="Full-text search query")
    history_parser.add_argument("--limit", type=int, default=50, choices=range(1, 10001), metavar="N", help="Max events to show (1-10000)")
    history_parser.add_argument("--json", dest="output_json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if args.command == "start":
        if args.host not in ("127.0.0.1", "localhost", "::1"):
            print("Warning: binding to non-loopback address exposes the agent to the network", file=sys.stderr)
        _start_agent(
            host=args.host,
            port=args.port,
            relay_key=args.relay_key,
            relay_url=args.relay_url,
        )
    elif args.command == "stop":
        _stop_agent(port=args.port)
    elif args.command == "mcp":
        _start_mcp()
    elif args.command == "analytics":
        if args.host not in ("127.0.0.1", "localhost", "::1"):
            print("Warning: binding to non-loopback address exposes the agent to the network", file=sys.stderr)
        _start_analytics(host=args.host, port=args.port)
    elif args.command == "history":
        _query_history(args)
    else:
        parser.print_help()
        sys.exit(1)


def _start_agent(host: str, port: int, relay_key: str = "", relay_url: str = "") -> None:
    import os
    import uvicorn

    print()
    print(f"  Bannin agent v0.1.0")
    print(f"  Dashboard:  http://{host}:{port}")
    print(f"  API docs:   http://{host}:{port}/docs")
    if relay_key:
        print(f"  Relay:      {relay_url}")
    print()

    # Pass relay config via environment variables so api.py lifespan can read them
    if relay_key:
        os.environ["BANNIN_RELAY_KEY"] = relay_key
        os.environ["BANNIN_RELAY_URL"] = relay_url

    uvicorn.run("bannin.api:app", host=host, port=port, log_level="warning")


def _stop_agent(port: int) -> None:
    """Stop a running Bannin agent by finding and terminating its process."""
    import psutil

    target_port = port
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            for conn in proc.net_connections(kind="tcp"):
                if conn.laddr.port == target_port and conn.status == "LISTEN":
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                        print(f"  Bannin agent (PID {proc.pid}) stopped.")
                    except psutil.TimeoutExpired:
                        proc.kill()
                        print(f"  Bannin agent (PID {proc.pid}) killed.")
                    return
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    print(f"  No Bannin agent found on port {target_port}.")
    sys.exit(1)


def _start_mcp() -> None:
    try:
        from bannin.mcp.server import serve
        serve()
    except ImportError:
        print("Error: MCP SDK not installed. Install with: pip install bannin[mcp]")
        sys.exit(1)


def _start_analytics(host: str, port: int) -> None:
    import uvicorn

    print()
    print(f"  Bannin Analytics Dashboard")
    print(f"  Dashboard:  http://{host}:{port}")
    print()

    uvicorn.run("bannin.analytics.api:app", host=host, port=port, log_level="warning")


def _query_history(args: argparse.Namespace) -> None:
    from bannin.analytics.store import AnalyticsStore
    store = AnalyticsStore.get()

    # Bound user-supplied filter strings to prevent oversized allocations
    search_q = args.search[:500] if args.search else ""
    event_type = args.type[:256] if args.type else ""
    severity = args.severity[:64] if args.severity else ""

    if search_q:
        events = store.search(search_q, limit=args.limit)
    else:
        since_ts = _parse_since(args.since)
        events = store.query(
            event_type=event_type or None,
            severity=severity or None,
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
                if val < 0 or not math.isfinite(val):
                    return None
                return time.time() - (val * mult)
            except ValueError:
                return None
    return None


if __name__ == "__main__":
    main()
