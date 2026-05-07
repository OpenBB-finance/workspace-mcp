"""Widget catalog discovery, schema, data, and lifecycle tools."""

from typing import Any

from fastmcp import FastMCP

from workspace_mcp.models import (
    CreateWidgetCommand,
    DeleteWidgetCommand,
    GetParamOptionsCommand,
    GetWidgetDataCommand,
    GetWidgetSchemaCommand,
    ListAvailableWidgetsCommand,
    ParamOptionsRequest,
    ReadWidgetCommand,
    UpdateDashboardLayoutCommand,
    UpdateWidgetCommand,
    WidgetDataRequest,
)
from workspace_mcp.server._guidance import (
    CREATE_WIDGET_GUIDANCE,
    DASHBOARD_TARGETING_GUIDANCE,
    DATA_SOURCE_SHAPE,
    EXISTING_DASHBOARD_GUIDANCE,
    PARAM_OPTIONS_SHAPE,
    WIDGET_INSTANCE_GUIDANCE,
    describe_tool,
)
from workspace_mcp.server._helpers import (
    CommandRunner,
    ToolResponse,
    data_source_payloads,
    has_layout_ui_args,
    invalid_request,
    is_generative_only_widget,
    param_options_payloads,
    required_widget_config,
    widget_config,
)


def register(server: FastMCP, run: CommandRunner) -> None:
    @server.tool(
        description=describe_tool(
            "Fetch current data for one or more Workspace data sources.",
            DATA_SOURCE_SHAPE,
            "Only use this after selecting an exact widget identity and explicit data_args.",
        )
    )
    async def get_widget_data(
        origin: str,
        widget_id: str,
        data_args: dict[str, Any] | None = None,
        widget_uuid: str | None = None,
        ssm_request: dict[str, Any] | None = None,
    ) -> ToolResponse:
        """Fetch widget data using the same browser-side path Ada uses."""
        return await run(
            GetWidgetDataCommand(
                command="get_widget_data",
                data_sources=data_source_payloads(
                    [
                        WidgetDataRequest(
                            origin=origin,
                            widget_id=widget_id,
                            data_args=data_args or {},
                            widget_uuid=widget_uuid,
                            ssm_request=ssm_request,
                        )
                    ]
                ),
            )
        )

    @server.tool(
        description=describe_tool(
            "List widgets available to the current Workspace session.",
            "Returns deterministic widget identities for later get_widget_schema and create_widget calls.",
            "Optional filters: origin matches the friendly catalog label exactly (e.g. 'Options Activity Monitor'), "
            "backend_id matches the backend UUID returned by manage_backends. "
            "Use backend_id when you have a UUID from manage_backends; use origin when working from a snapshot. "
            "Both can be passed together for a stricter match. Without filters the entire catalog is returned, "
            "which can be hundreds of widgets — prefer a filter when you know the source.",
            "Generative-only note widgets such as rich_note are intentionally excluded; use add_generative_widget for those.",
            "Widgets that still require runtime-only bootstrap are also excluded until their plain create contract is deterministic.",
        )
    )
    async def list_available_widgets(
        origin: str | None = None,
        backend_id: str | None = None,
    ) -> ToolResponse:
        """List widgets that can be created in the current Workspace session."""
        return await run(
            ListAvailableWidgetsCommand(
                command="list_available_widgets",
                origin=origin,
                backend_id=backend_id,
            )
        )

    @server.tool(
        description=describe_tool(
            "Fetch the exact schema for one available widget.",
            "Pass origin and widget_id from list_available_widgets or the workspace snapshot.",
            "If you need a rich text note, use add_generative_widget with widget_type='note' instead of get_widget_schema on rich_note.",
            "The response includes grid_data when layout defaults or min/max constraints are defined for that widget.",
            "If a param returns requires_options_lookup=true, call get_params_options before using that param in create_widget or update_widget.",
        )
    )
    async def get_widget_schema(
        origin: str | None = None,
        widget_id: str | None = None,
    ) -> ToolResponse:
        """Fetch one deterministic widget schema from the Workspace widget library."""
        if not origin or not widget_id:
            return invalid_request(
                "get_widget_schema",
                "get_widget_schema requires origin from list_available_widgets and widget_id.",
            )
        return await run(
            GetWidgetSchemaCommand(
                command="get_widget_schema",
                origin=origin,
                widget_id=widget_id,
            )
        )

    @server.tool(
        description=describe_tool(
            "Fetch parameter options for one or more widget input queries.",
            PARAM_OPTIONS_SHAPE,
            "Use this when get_widget_schema marks a param with requires_options_lookup=true.",
        )
    )
    async def get_params_options(
        origin: str,
        widget_id: str,
        param_name: str,
        data_args: dict[str, Any] | None = None,
    ) -> ToolResponse:
        """Fetch parameter options from the browser bridge."""
        return await run(
            GetParamOptionsCommand(
                command="get_params_options",
                param_options_queries=param_options_payloads(
                    [
                        ParamOptionsRequest(
                            origin=origin,
                            widget_id=widget_id,
                            param_name=param_name,
                            data_args=data_args or {},
                        )
                    ]
                ),
            )
        )

    @server.tool(
        description=describe_tool(
            "Read one widget from the active dashboard.",
            WIDGET_INSTANCE_GUIDANCE,
        )
    )
    async def read_widget(
        widget_uuid: str | None = None,
        widget_id: str | None = None,
        dashboard_id: str | None = None,
    ) -> ToolResponse:
        """Load one widget's current payload from Workspace.

        ``widget_uuid`` is the canonical instance identifier. ``widget_id`` is
        accepted as a fallback alias for callers that only know the widget type
        identifier and need the browser bridge to resolve the active instance.
        """
        return await run(
            ReadWidgetCommand(
                command="read_widget",
                widget_uuid=widget_uuid,
                widget_id=widget_id,
                dashboard_id=dashboard_id,
            )
        )

    @server.tool(
        description=describe_tool(
            "Create one widget on a target dashboard.",
            "Requires origin and widget_id.",
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
            "Use list_available_widgets and get_widget_schema first.",
            CREATE_WIDGET_GUIDANCE,
            "Do not use this for rich_note; use add_generative_widget with widget_type='note'.",
        )
    )
    async def create_widget(
        origin: str | None = None,
        widget_id: str | None = None,
        dashboard_id: str | None = None,
        data_args: dict[str, Any] | None = None,
        ui_args: dict[str, Any] | None = None,
    ) -> ToolResponse:
        """Create a new Workspace widget."""
        if not origin or not widget_id:
            return invalid_request(
                "create_widget",
                "create_widget requires origin from list_available_widgets and widget_id.",
            )
        if is_generative_only_widget(widget_id):
            return invalid_request(
                "create_widget",
                "create_widget does not support 'rich_note'. "
                "Use add_generative_widget with widget_type='note' instead.",
            )
        return await run(
            CreateWidgetCommand(
                command="create_widget",
                dashboard_id=dashboard_id,
                backend_name=origin,
                widget_id=widget_id,
                config=widget_config(
                    data_args=data_args or None,
                    ui_args=ui_args or None,
                ),
            )
        )

    @server.tool(
        description=describe_tool(
            "Update one existing widget on a target dashboard.",
            WIDGET_INSTANCE_GUIDANCE,
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
        )
    )
    async def update_widget(
        widget_uuid: str | None = None,
        widget_id: str | None = None,
        dashboard_id: str | None = None,
        data_args: dict[str, Any] | None = None,
        ui_args: dict[str, Any] | None = None,
    ) -> ToolResponse:
        """Update an existing Workspace widget."""
        if has_layout_ui_args(ui_args):
            return invalid_request(
                "update_widget",
                "update_widget only supports widget-instance config changes. "
                "Use update_widget_layout for x, y, w, h, gridData, or tab_id.",
            )
        return await run(
            UpdateWidgetCommand(
                command="update_widget",
                dashboard_id=dashboard_id,
                widget_uuid=widget_uuid,
                widget_id=widget_id,
                config=required_widget_config(
                    data_args=data_args or None,
                    ui_args=ui_args or None,
                ),
            )
        )

    @server.tool(
        description=describe_tool(
            "Move or resize one widget in dashboard layout space.",
            "Requires x, y, w, and h. Use tab_id from manage_dashboard operation='read' or get_workspace_snapshot.dashboard_composition when moving across tabs.",
            "The layout grid is 40 columns wide: full width is w=40, half width is w=20, one quarter is w=10. If a navigation_bar is present, first content usually starts at y=2.",
            WIDGET_INSTANCE_GUIDANCE,
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
        )
    )
    async def update_widget_layout(
        x: float,
        y: float,
        w: float,
        h: float,
        widget_uuid: str | None = None,
        widget_id: str | None = None,
        dashboard_id: str | None = None,
        tab_id: str | None = None,
        min_w: float | None = None,
        min_h: float | None = None,
        max_w: float | None = None,
        max_h: float | None = None,
    ) -> ToolResponse:
        """Move or resize one widget in dashboard layout space."""
        return await run(
            UpdateDashboardLayoutCommand(
                command="update_dashboard_layout",
                dashboard_id=dashboard_id,
                widget_uuid=widget_uuid,
                widget_id=widget_id,
                tab_id=tab_id,
                x=x,
                y=y,
                w=w,
                h=h,
                min_w=min_w,
                min_h=min_h,
                max_w=max_w,
                max_h=max_h,
            )
        )

    @server.tool(
        description=describe_tool(
            "Delete one widget from a target dashboard.",
            WIDGET_INSTANCE_GUIDANCE,
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
        )
    )
    async def delete_widget(
        widget_uuid: str | None = None,
        widget_id: str | None = None,
        dashboard_id: str | None = None,
    ) -> ToolResponse:
        """Delete a Workspace widget."""
        return await run(
            DeleteWidgetCommand(
                command="delete_widget",
                dashboard_id=dashboard_id,
                widget_uuid=widget_uuid,
                widget_id=widget_id,
            )
        )
