"""Navigation-bar mutation and route navigation tools."""

from typing import Any, cast

from fastmcp import FastMCP

from workspace_mcp.models import (
    ManageNavigationBarCommand,
    NavigateWorkspaceCommand,
    NavigationTabInput,
)
from workspace_mcp.server._guidance import (
    DASHBOARD_TARGETING_GUIDANCE,
    EXISTING_DASHBOARD_GUIDANCE,
    NAVIGATION_BAR_GUIDANCE,
    describe_tool,
)
from workspace_mcp.server._helpers import (
    CommandRunner,
    NavigationOperationName,
    ToolResponse,
    invalid_request,
)


def register(server: FastMCP, run: CommandRunner) -> None:
    @server.tool(
        description=describe_tool(
            "Create or mutate the Workspace navigation bar.",
            "Requires operation from {create, add_tabs, remove_tabs, rename_tabs}.",
            'For create, add_tabs, and remove_tabs, pass tabs as an array of objects, for example [{"name":"AAPL Analysis"}].',
            'The only tab-object field is name; tab_id and tab_name are rejected. The tab_id is generated as the slug of name.',
            'Do not pass tabs as ["AAPL Analysis"]; string arrays are rejected.',
            'After add_tabs, navigate to the generated slug tab_id, e.g. AAPL Analysis -> aapl-analysis, before creating content for that tab.',
            'For rename_tabs, pass rename_map as an object, for example {"old-tab-id":"New Name"}.',
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
            NAVIGATION_BAR_GUIDANCE,
        )
    )
    async def manage_navigation_bar(
        operation: str,
        dashboard_id: str | None = None,
        tabs: list[NavigationTabInput] | None = None,
        rename_map: dict[str, str] | None = None,
    ) -> ToolResponse:
        """Create tabs or update navigation tab metadata."""
        allowed_operations: set[NavigationOperationName] = {
            "create",
            "add_tabs",
            "remove_tabs",
            "rename_tabs",
        }
        if operation not in allowed_operations:
            return invalid_request(
                "manage_navigation_bar",
                "manage_navigation_bar requires operation from {create, add_tabs, remove_tabs, rename_tabs}.",
            )
        tabs_payload = [tab.model_dump() for tab in (tabs or [])]
        rename_map_payload = rename_map or {}
        if operation in {"create", "add_tabs", "remove_tabs"} and not tabs_payload:
            return invalid_request(
                "manage_navigation_bar",
                f"manage_navigation_bar operation='{operation}' requires tabs.",
            )
        if operation == "rename_tabs" and not rename_map_payload:
            return invalid_request(
                "manage_navigation_bar",
                "manage_navigation_bar operation='rename_tabs' requires rename_map.",
            )
        return await run(
            ManageNavigationBarCommand(
                command="manage_navigation_bar",
                dashboard_id=dashboard_id,
                operation=cast(Any, operation),
                tabs=tabs_payload,
                rename_map=rename_map_payload,
            )
        )

    @server.tool(
        description=describe_tool(
            "Navigate the Workspace browser to an existing dashboard or inner tab.",
            "Requires operation from {dashboard, tab}.",
            "For operation='dashboard', pass dashboard_id and optional tab_id.",
            "For operation='tab', pass tab_id and optional dashboard_id; omitted dashboard_id targets the current dashboard route.",
            EXISTING_DASHBOARD_GUIDANCE,
        )
    )
    async def navigate_workspace(
        operation: str,
        dashboard_id: str | None = None,
        tab_id: str | None = None,
    ) -> ToolResponse:
        """Navigate to a dashboard route or switch an inner tab."""
        if operation == "dashboard":
            if not dashboard_id:
                return invalid_request(
                    "navigate_workspace",
                    "navigate_workspace operation='dashboard' requires dashboard_id.",
                )
            return await run(
                NavigateWorkspaceCommand(
                    command="navigate_workspace",
                    operation="dashboard",
                    dashboard_id=dashboard_id,
                    tab_id=tab_id,
                )
            )
        if operation == "tab":
            if not tab_id:
                return invalid_request(
                    "navigate_workspace",
                    "navigate_workspace operation='tab' requires tab_id.",
                )
            return await run(
                NavigateWorkspaceCommand(
                    command="navigate_workspace",
                    operation="tab",
                    tab_id=tab_id,
                    dashboard_id=dashboard_id,
                )
            )
        return invalid_request(
            "navigate_workspace",
            "navigate_workspace requires operation from {dashboard, tab}.",
        )
