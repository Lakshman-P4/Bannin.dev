import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="bannin",
        description="Bannin — universal monitoring agent",
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

    args = parser.parse_args()

    if args.command == "start":
        _start_agent(host=args.host, port=args.port)
    elif args.command == "mcp":
        _start_mcp()
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


if __name__ == "__main__":
    main()
