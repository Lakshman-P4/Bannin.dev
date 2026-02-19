"""Run the Bannin MCP server via stdio transport.

Usage:
    python -m bannin.mcp
"""

import sys


def main():
    try:
        from bannin.mcp.server import serve
    except ImportError:
        print(
            "Error: MCP SDK not installed. Install with: pip install bannin[mcp]",
            file=sys.stderr,
        )
        sys.exit(1)
    serve()


if __name__ == "__main__":
    main()
