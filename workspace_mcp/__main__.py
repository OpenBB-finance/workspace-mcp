"""CLI entrypoint for the Workspace MCP sidecar."""

import argparse

import uvicorn

from workspace_mcp.app import create_app
from workspace_mcp.config import Settings


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the sidecar."""
    parser = argparse.ArgumentParser(
        description="Run the OpenBB Workspace MCP sidecar.",
        epilog="Example: workspace-mcp --host 127.0.0.1 --port 8787 --mcp-path /mcp",
    )
    parser.add_argument(
        "-H",
        "--host",
        default="127.0.0.1",
        help="Host interface for the sidecar HTTP server.",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8787,
        help="Port for the sidecar HTTP server.",
    )
    parser.add_argument(
        "-m",
        "--mcp-path",
        default="/mcp",
        help="Path for the FastMCP streamable HTTP endpoint.",
    )
    parser.add_argument(
        "-t",
        "--command-timeout-seconds",
        type=float,
        default=15.0,
        help="Seconds to wait for one browser command result.",
    )
    return parser


def main() -> None:
    """Run the sidecar server."""
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings(
        host=args.host,
        port=args.port,
        mcp_path=args.mcp_path,
        command_timeout_seconds=args.command_timeout_seconds,
    )
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
