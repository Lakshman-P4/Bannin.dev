"""Run the Bannin MCP server via stdio transport.

Usage:
    python -m bannin.mcp
"""

from __future__ import annotations

import sys


def main() -> None:
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
