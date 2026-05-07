"""Backend connection management and app-template tools."""

from typing import Any, cast

from fastmcp import FastMCP

from workspace_mcp.models import (
    BackendEndpointHeader,
    ManageAppsCommand,
    ManageBackendsCommand,
)
from workspace_mcp.server._guidance import describe_tool
from workspace_mcp.server._helpers import (
    CommandRunner,
    ToolResponse,
    invalid_request,
)


def register(server: FastMCP, run: CommandRunner) -> None:
    @server.tool(
        description=describe_tool(
            "Manage Workspace data backends (the connections that power widgets).",
            "Requires operation from {list, add, update, refresh, remove}.",
            "For list, returns each backend with id, name, url, status, and widget/app/agent counts.",
            "For add, requires name and url. Optional endpoint_headers is an array of "
            '{"key", "value", "location"} objects where location is "headers" (default) or "query". '
            "validate_widgets defaults to true and surfaces a warning if widgets fail to load.",
            "For update, requires backend_id and at least one of name, url, or endpoint_headers.",
            "For refresh, requires backend_id; re-fetches widgets and templates from the backend URL.",
            "For remove, requires backend_id.",
        )
    )
    async def manage_backends(
        operation: str,
        backend_id: str | None = None,
        name: str | None = None,
        url: str | None = None,
        endpoint_headers: list[BackendEndpointHeader] | None = None,
        validate_widgets: bool | None = None,
        is_openbb_platform: bool | None = None,
    ) -> ToolResponse:
        """List, add, update, refresh, or remove Workspace data backends."""
        allowed_operations: set[str] = {"list", "add", "update", "refresh", "remove"}
        if operation not in allowed_operations:
            return invalid_request(
                "manage_backends",
                "manage_backends requires operation from {list, add, update, refresh, remove}.",
            )

        if operation == "add":
            if not name or not url:
                return invalid_request(
                    "manage_backends",
                    "manage_backends operation='add' requires name and url.",
                )
        elif operation in {"update", "refresh", "remove"}:
            if not backend_id:
                return invalid_request(
                    "manage_backends",
                    f"manage_backends operation='{operation}' requires backend_id.",
                )
            if operation == "update" and not (
                name
                or url
                or endpoint_headers is not None
                or is_openbb_platform is not None
            ):
                return invalid_request(
                    "manage_backends",
                    "manage_backends operation='update' requires at least one of "
                    "name, url, endpoint_headers, or is_openbb_platform.",
                )

        return await run(
            ManageBackendsCommand(
                command="manage_backends",
                operation=cast(Any, operation),
                backend_id=backend_id,
                name=name,
                url=url,
                endpoint_headers=endpoint_headers,
                validate_widgets=validate_widgets,
                is_openbb_platform=is_openbb_platform,
            )
        )

    @server.tool(
        description=describe_tool(
            "List, read, or instantiate apps from a Workspace data backend.",
            "Apps are full dashboard templates declared in the backend's apps.json: "
            "they bundle tabs, widget layouts, parameter groups, and suggested prompts. "
            "Instantiating one is the programmatic equivalent of clicking an app in the gallery.",
            "Requires operation from {list, read, instantiate} and backend_id. "
            "Use manage_backends operation='list' to discover backend_id values and app_count.",
            "For list, returns each app with name, template_id, description, tab_count, "
            "group_count, prompt_count, and allow_customization.",
            "For read, requires app_name (or template_id); returns the full app definition "
            "including tabs with layouts, parameter groups, and suggested prompts.",
            "For instantiate, requires app_name (or template_id); creates a fresh dashboard "
            "from the app template and returns its dashboard_id. Pass that dashboard_id to "
            "subsequent dashboard-targeting tools. activate defaults to true and routes the "
            "browser to the new dashboard.",
        )
    )
    async def manage_apps(
        operation: str,
        backend_id: str,
        app_name: str | None = None,
        template_id: str | None = None,
        dashboard_name: str | None = None,
        activate: bool | None = None,
    ) -> ToolResponse:
        """List, read, or instantiate apps declared in a backend's apps.json."""
        allowed_operations: set[str] = {"list", "read", "instantiate"}
        if operation not in allowed_operations:
            return invalid_request(
                "manage_apps",
                "manage_apps requires operation from {list, read, instantiate}.",
            )
        if not backend_id:
            return invalid_request(
                "manage_apps",
                "manage_apps requires backend_id.",
            )
        if operation in {"read", "instantiate"} and not app_name and not template_id:
            return invalid_request(
                "manage_apps",
                f"manage_apps operation='{operation}' requires app_name or template_id.",
            )

        return await run(
            ManageAppsCommand(
                command="manage_apps",
                operation=cast(Any, operation),
                backend_id=backend_id,
                app_name=app_name,
                template_id=template_id,
                dashboard_name=dashboard_name,
                activate=activate,
            )
        )
