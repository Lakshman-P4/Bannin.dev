import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="vigilo",
        description="Vigilo — universal monitoring agent",
    )
    subparsers = parser.add_subparsers(dest="command")

    start_parser = subparsers.add_parser("start", help="Start the Vigilo agent")
    start_parser.add_argument(
        "--port", type=int, default=8420, help="Port to run on (default: 8420)"
    )
    start_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )

    args = parser.parse_args()

    if args.command == "start":
        _start_agent(host=args.host, port=args.port)
    else:
        parser.print_help()
        sys.exit(1)


def _start_agent(host: str, port: int):
    import uvicorn

    print(f"  Vigilo agent v0.1.0")
    print(f"  Listening on http://{host}:{port}")
    print(f"  Endpoints:")
    print(f"    GET /metrics    — system metrics (CPU, RAM, disk, GPU)")
    print(f"    GET /status     — agent info")
    print(f"    GET /processes  — top processes by CPU usage")
    print(f"    GET /tasks      — monitored tasks (coming soon)")
    print(f"    GET /health     — health check")
    print()

    uvicorn.run("vigilo.api:app", host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
