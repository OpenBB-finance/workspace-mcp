"""FastMCP tool surface for the Workspace sidecar."""

from typing import Any, cast

from fastmcp import FastMCP

from workspace_mcp.models import (
    AddGenerativeWidgetCommand,
    CreateWidgetCommand,
    DeleteWidgetCommand,
    ManageNavigationBarCommand,
    ReadWidgetCommand,
    UpdateWidgetCommand,
    WorkspaceWidgetConfig,
)
from workspace_mcp.state import BrowserUnavailableError, BridgeSessionManager

type ToolResponse = dict[str, Any]


def widget_config(
    *,
    data_args: dict[str, Any] | None,
    ui_args: dict[str, Any] | None,
) -> WorkspaceWidgetConfig | None:
    """Build widget config only when the caller supplied config values."""
    if data_args is None and ui_args is None:
        return None
    return WorkspaceWidgetConfig(data_args=data_args, ui_args=ui_args)


def required_widget_config(
    *, data_args: dict[str, Any] | None, ui_args: dict[str, Any] | None
) -> WorkspaceWidgetConfig:
    """Build widget config for commands that always expect the field."""
    return widget_config(data_args=data_args, ui_args=ui_args) or WorkspaceWidgetConfig()


def create_mcp_server(state: BridgeSessionManager) -> FastMCP:
    """Create the Workspace MCP server with a flat v1 tool list."""
    server = FastMCP(
        name="OpenBB Workspace MCP",
        instructions=(
            "Expose the active OpenBB Workspace browser session as MCP tools. "
            "All tools require a running local Workspace browser bridge."
        ),
    )

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

    @server.tool(
        description=(
            "Request a fresh OpenBB Workspace snapshot from the connected browser."
        )
    )
    async def get_workspace_snapshot(
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Fetch the current workspace snapshot from the connected browser."""
        _ = wait_for_previous
        return await run({"command": "get_workspace_snapshot"})

    @server.tool(description="Read one widget from the active dashboard by widget UUID.")
    async def read_widget(
        widget_uuid: str,
        dashboard_id: str | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Load one widget's current payload from Workspace."""
        _ = wait_for_previous
        return await run(
            ReadWidgetCommand(
                command="read_widget",
                widget_uuid=widget_uuid,
                dashboard_id=dashboard_id,
            )
        )

    @server.tool(description="Create one widget on the active dashboard.")
    async def create_widget(
        dashboard_id: str,
        backend_name: str,
        widget_id: str,
        data_args: dict[str, Any] | None = None,
        ui_args: dict[str, Any] | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Create a new Workspace widget."""
        _ = wait_for_previous
        return await run(
            CreateWidgetCommand(
                command="create_widget",
                dashboard_id=dashboard_id,
                backend_name=backend_name,
                widget_id=widget_id,
                config=widget_config(data_args=data_args, ui_args=ui_args),
            )
        )

    @server.tool(description="Update one existing widget on the active dashboard.")
    async def update_widget(
        dashboard_id: str,
        widget_uuid: str,
        data_args: dict[str, Any] | None = None,
        ui_args: dict[str, Any] | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Update an existing Workspace widget."""
        _ = wait_for_previous
        return await run(
            UpdateWidgetCommand(
                command="update_widget",
                dashboard_id=dashboard_id,
                widget_uuid=widget_uuid,
                config=required_widget_config(data_args=data_args, ui_args=ui_args),
            )
        )

    @server.tool(description="Delete one widget from the active dashboard.")
    async def delete_widget(
        dashboard_id: str,
        widget_uuid: str,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Delete a Workspace widget."""
        _ = wait_for_previous
        return await run(
            DeleteWidgetCommand(
                command="delete_widget",
                dashboard_id=dashboard_id,
                widget_uuid=widget_uuid,
            )
        )

    @server.tool(description="Create or mutate the Workspace navigation bar.")
    async def manage_navigation_bar(
        dashboard_id: str,
        operation: str,
        tabs: list[dict[str, Any]] | None = None,
        rename_map: dict[str, str] | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Create tabs or update navigation tab metadata."""
        _ = wait_for_previous
        return await run(
            ManageNavigationBarCommand(
                command="manage_navigation_bar",
                dashboard_id=dashboard_id,
                operation=cast(Any, operation),
                tabs=tabs or [],
                rename_map=rename_map or {},
            )
        )

    @server.tool(description="Create a generated note, table, chart, or HTML widget.")
    async def add_generative_widget(
        dashboard_id: str,
        widget_type: str,
        data: list[dict[str, Any]] | str | None = None,
        name: str | None = None,
        description: str | None = None,
        chart_params: dict[str, Any] | None = None,
        inner_tab: str | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Create a generative widget from inline content."""
        _ = wait_for_previous
        return await run(
            AddGenerativeWidgetCommand(
                command="add_generative_widget",
                dashboard_id=dashboard_id,
                widget_type=cast(Any, widget_type),
                data=data,
                name=name,
                description=description,
                chart_params=chart_params,
                inner_tab=inner_tab,
            )
        )

    return server
