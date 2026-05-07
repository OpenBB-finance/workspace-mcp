"""FastMCP tool surface for the Workspace sidecar.

This package wires the per-domain tool modules into a single ``FastMCP``
instance. The public entry point is ``create_mcp_server``; the rest of the
re-exports keep ``from workspace_mcp.server import ...`` working for callers
that depend on the original flat-module layout (notably the test suite).
"""

from typing import Any

from fastmcp import FastMCP

from workspace_mcp.app_builder import register_app_builder_resources
from workspace_mcp.server._guidance import SERVER_INSTRUCTIONS, describe_tool
from workspace_mcp.server._helpers import (
    CommandRunner,
    ToolResponse,
    data_source_payloads,
    has_layout_ui_args,
    invalid_request,
    is_generative_only_widget,
    param_options_payloads,
    payload_list,
    required_widget_config,
    session_context_prompt_content,
    validate_add_generative_widget_request,
    widget_config,
)
from workspace_mcp.server.tools import (
    agents as agents_tools,
    backends as backends_tools,
    dashboards as dashboards_tools,
    generative as generative_tools,
    navigation as navigation_tools,
    snapshot as snapshot_tools,
    widgets as widgets_tools,
)
from workspace_mcp.state import BridgeSessionManager, BrowserUnavailableError


__all__ = [
    "SERVER_INSTRUCTIONS",
    "ToolResponse",
    "create_mcp_server",
    "data_source_payloads",
    "describe_tool",
    "has_layout_ui_args",
    "invalid_request",
    "is_generative_only_widget",
    "param_options_payloads",
    "payload_list",
    "required_widget_config",
    "session_context_prompt_content",
    "validate_add_generative_widget_request",
    "widget_config",
]


def create_mcp_server(state: BridgeSessionManager) -> FastMCP:
    """Create the Workspace MCP server with the full v1 tool list."""
    server = FastMCP(
        name="OpenBB Workspace MCP",
        instructions=SERVER_INSTRUCTIONS,
    )

    register_app_builder_resources(server)

    @server.prompt(
        name="workspace_tool_usage",
        description="Generic guidance for using the OpenBB Workspace MCP tool surface.",
    )
    def workspace_tool_usage() -> list[dict[str, str]]:
        """Return a compact, generic usage prompt for MCP agents."""
        return [
            {"role": "user", "content": SERVER_INSTRUCTIONS},
            {"role": "user", "content": session_context_prompt_content(state)},
        ]

    @server.prompt(
        name="workspace_session_context",
        description="Current tracked Workspace dashboard and tab context.",
    )
    def workspace_session_context() -> list[dict[str, str]]:
        """Return the current tracked Workspace dashboard and tab context."""
        return [{"role": "user", "content": session_context_prompt_content(state)}]

    async def run(command: Any) -> ToolResponse:
        try:
            result = await state.execute_command(command)
        except BrowserUnavailableError as error:
            return {
                "ok": False,
                "message": str(error),
                "error": {"code": "unavailable", "message": str(error)},
            }
        return result.model_dump(mode="json")

    runner: CommandRunner = run

    snapshot_tools.register(server, runner)
    widgets_tools.register(server, runner)
    dashboards_tools.register(server, runner)
    navigation_tools.register(server, runner)
    generative_tools.register(server, runner)
    backends_tools.register(server, runner)
    agents_tools.register(server, runner)

    return server
