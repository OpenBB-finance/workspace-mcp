"""Generated note/table/chart/HTML widget tool."""

from typing import Any, cast

from fastmcp import FastMCP

from workspace_mcp.models import AddGenerativeWidgetCommand
from workspace_mcp.server._guidance import (
    DASHBOARD_TARGETING_GUIDANCE,
    EXISTING_DASHBOARD_GUIDANCE,
    GENERATIVE_WIDGET_GUIDANCE,
    describe_tool,
)
from workspace_mcp.server._helpers import (
    CommandRunner,
    GenerativeWidgetTypeName,
    ToolResponse,
    invalid_request,
    validate_add_generative_widget_request,
)


def register(server: FastMCP, run: CommandRunner) -> None:
    @server.tool(
        description=describe_tool(
            "Create a generated note, table, chart, or HTML widget.",
            "Requires widget_type from {note, table, chart, html}.",
            "inner_tab targets an existing navigation tab only; it does not create a new tab.",
            'For a new tab workflow, call manage_navigation_bar operation="add_tabs" with tabs like [{"name":"AAPL Analysis"}], navigate_workspace to the generated slug tab_id, then call add_generative_widget without inner_tab.',
            "data shape depends on widget_type: note/html accept a string; table/chart accept an array of objects.",
            "chart_params (for chart widgets) is an object with camelCase keys: chartType, xKey, yKey (array), and optional angleKey/calloutLabelKey.",
            GENERATIVE_WIDGET_GUIDANCE,
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
        )
    )
    async def add_generative_widget(
        widget_type: str,
        dashboard_id: str | None = None,
        data: str | list[dict[str, Any]] | None = None,
        name: str | None = None,
        description: str | None = None,
        chart_params: dict[str, Any] | None = None,
        inner_tab: str | None = None,
    ) -> ToolResponse:
        """Create a generative widget from inline content."""
        allowed_widget_types: set[GenerativeWidgetTypeName] = {
            "note",
            "table",
            "chart",
            "html",
        }
        if widget_type not in allowed_widget_types:
            return invalid_request(
                "add_generative_widget",
                "add_generative_widget requires widget_type from {note, table, chart, html}.",
            )
        payload_error = validate_add_generative_widget_request(
            widget_type=widget_type,
            data=data,
            chart_params=chart_params,
        )
        if payload_error:
            return invalid_request("add_generative_widget", payload_error)
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
