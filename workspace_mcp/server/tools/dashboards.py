"""Dashboard CRUD tool."""

from fastmcp import FastMCP

from workspace_mcp.models import ManageDashboardCommand
from workspace_mcp.server._guidance import describe_tool
from workspace_mcp.server._helpers import CommandRunner, ToolResponse, invalid_request


def register(server: FastMCP, run: CommandRunner) -> None:
    @server.tool(
        description=describe_tool(
            "Create, read, or update one Workspace dashboard.",
            "Requires operation from {create, read, update}.",
            "For create, pass name and optional dashboard_id and activate.",
            "For read, pass optional dashboard_id; omitted dashboard_id targets the current dashboard route.",
            "For update, pass dashboard_id and name.",
        )
    )
    async def manage_dashboard(
        operation: str,
        dashboard_id: str | None = None,
        name: str | None = None,
        activate: bool | None = None,
    ) -> ToolResponse:
        """Create, read, or update dashboard metadata and composition."""
        if operation == "create":
            if not name:
                return invalid_request(
                    "manage_dashboard",
                    "manage_dashboard operation='create' requires name.",
                )
            return await run(
                ManageDashboardCommand(
                    command="manage_dashboard",
                    operation="create",
                    name=name,
                    dashboard_id=dashboard_id,
                    activate=True if activate is None else activate,
                )
            )
        if operation == "read":
            return await run(
                ManageDashboardCommand(
                    command="manage_dashboard",
                    operation="read",
                    dashboard_id=dashboard_id,
                )
            )
        if operation == "update":
            if not dashboard_id or name is None:
                return invalid_request(
                    "manage_dashboard",
                    "manage_dashboard operation='update' requires dashboard_id and name.",
                )
            return await run(
                ManageDashboardCommand(
                    command="manage_dashboard",
                    operation="update",
                    dashboard_id=dashboard_id,
                    name=name,
                )
            )
        return invalid_request(
            "manage_dashboard",
            "manage_dashboard requires operation from {create, read, update}.",
        )
