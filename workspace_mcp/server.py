"""FastMCP tool surface for the Workspace sidecar."""

from typing import Any, cast

from fastmcp import FastMCP

from workspace_mcp.models import (
    AddGenerativeWidgetCommand,
    AssignTasksToAgentsCommand,
    CreateDashboardCommand,
    CreateWidgetCommand,
    DeleteWidgetCommand,
    ExecuteAgentToolCommand,
    GetParamOptionsCommand,
    GetSkillContentCommand,
    GetWidgetDataCommand,
    GetWidgetSchemaCommand,
    ListAvailableWidgetsCommand,
    ManageNavigationBarCommand,
    ParamOptionsRequest,
    ReadDashboardCommand,
    ReadWidgetCommand,
    UpdateDashboardLayoutCommand,
    UpdateDashboardCommand,
    UpdateWidgetCommand,
    WidgetDataRequest,
    WorkspaceWidgetConfig,
)
from workspace_mcp.state import BrowserUnavailableError, BridgeSessionManager

type ToolResponse = dict[str, Any]
type NavigationOperationName = str
type GenerativeWidgetTypeName = str

USAGE_SUMMARY = (
    "Use snake_case payloads. Start with get_workspace_snapshot to discover valid "
    "dashboard_id, dashboard_composition, and skills from the live Workspace "
    "session. Use list_available_widgets and get_widget_schema for widget library "
    "discovery. Do not invent identifiers."
)
WIDGET_SCHEMA_GUIDANCE = (
    "Use list_available_widgets to enumerate candidates and get_widget_schema to "
    "inspect one exact widget contract before creating it. get_widget_schema "
    "includes grid_data defaults and min/max layout constraints when the widget "
    "definition provides them. If a param returns requires_options_lookup=true, "
    "call get_params_options before create_widget or update_widget and do not "
    "invent values for that param. Always pass the origin returned by "
    "list_available_widgets; blank origin means the catalog is invalid."
)
CREATE_WIDGET_GUIDANCE = (
    "For create_widget, pass origin as the exact catalog value returned by "
    "list_available_widgets. backend_name is accepted as a legacy alias, but "
    "origin is the canonical MCP field. data_args and ui_args must be native "
    "objects, not JSON strings."
)
DATA_SOURCE_SHAPE = (
    "Use data_sources items shaped like {origin, widget_id, data_args, "
    "widget_uuid?, ssm_request?}. Pass data_sources as a native array, not a "
    "JSON string."
)
PARAM_OPTIONS_SHAPE = (
    "Use param_options_queries items shaped like {origin, widget_id, "
    "param_name, data_args}. Pass param_options_queries as a native array, "
    "not a JSON string. Prefer one query at a time for large option sets."
)
GENERATIVE_WIDGET_GUIDANCE = (
    "For add_generative_widget: note and html require string data. "
    "table requires a native list[dict] data array. chart requires a native "
    "list[dict] data array plus "
    "chart_params with chartType, xKey, and non-empty yKey. "
    "Use widget_type='note' for rich text notes such as rich_note. "
    "The response includes widget_uuid; use that UUID for layout changes."
)
WIDGET_INSTANCE_GUIDANCE = (
    "Prefer widget_uuid for read, update, and delete. widget_id is only a fallback "
    "when exactly one matching widget instance exists on the target dashboard. "
    "Never use a widget title or generic widget type such as rich_note as a layout "
    "identifier."
)
DASHBOARD_TARGETING_GUIDANCE = (
    "To target the current dashboard route, omit dashboard_id. Do not send placeholder "
    "strings such as active_dashboard, current_dashboard, null, or undefined."
)
EXISTING_DASHBOARD_GUIDANCE = (
    "These tools operate on an existing dashboard only. They do not create dashboards."
)
CREATE_DASHBOARD_GUIDANCE = (
    "Use create_dashboard to create a dashboard first. By default it activates the "
    "new dashboard route so follow-up snapshot and widget commands target it."
)
LAYOUT_GUIDANCE = (
    "Visible placement is controlled by dashboard composition, not update_widget. "
    "Use read_dashboard or get_workspace_snapshot.dashboard_composition to inspect "
    "tabs and layout, then use update_dashboard_layout for x, y, w, h, and tab_id. "
    "The grid is 40 columns wide: full width is w=40, half width is w=20, one quarter "
    "is w=10. Typical minimums are about min_w=8 and min_h=4. If a navigation_bar is "
    "present it usually occupies y=0 with h=2, so the first content row usually starts "
    "at y=2."
)
NAVIGATION_BAR_GUIDANCE = (
    "manage_navigation_bar manages the navigation_bar widget inside an existing dashboard. "
    "If the dashboard does not already have a navigation_bar widget, call create first. "
    "Its create operation creates or initializes navigation tabs on that dashboard; it does not create a dashboard."
)
DISCOVERY_WORKFLOW = (
    "Recommended workflow: call get_workspace_snapshot first, create_dashboard when "
    "you need a fresh dashboard, call list_available_widgets to enumerate candidate "
    "widgets, call get_widget_schema for the exact widget contract, call "
    "get_params_options when a schema field returns requires_options_lookup=true, then call "
    "create_widget with explicit dashboard_id, origin, widget_id, data_args, and "
    "ui_args. list_available_widgets only returns the deterministic plain-create "
    "subset; widgets that still need runtime-only bootstrap are intentionally "
    "excluded. Do not use create_widget for rich_note; use add_generative_widget "
    "with widget_type='note'. Use read_dashboard or "
    "get_workspace_snapshot.dashboard_composition "
    "to inspect visible layout and update_dashboard_layout to move or resize "
    "widgets."
)
SERVER_INSTRUCTIONS = " ".join(
    [
        "Expose the active OpenBB Workspace browser session as MCP tools.",
        "All tools require a running local Workspace browser bridge.",
        USAGE_SUMMARY,
        WIDGET_SCHEMA_GUIDANCE,
        CREATE_WIDGET_GUIDANCE,
        DATA_SOURCE_SHAPE,
        PARAM_OPTIONS_SHAPE,
        GENERATIVE_WIDGET_GUIDANCE,
        WIDGET_INSTANCE_GUIDANCE,
        DASHBOARD_TARGETING_GUIDANCE,
        CREATE_DASHBOARD_GUIDANCE,
        LAYOUT_GUIDANCE,
        DISCOVERY_WORKFLOW,
        (
            "Provide dashboard_id explicitly when operating on a dashboard other than "
            "the current Workspace route."
        ),
    ]
)


def describe_tool(summary: str, *notes: str) -> str:
    """Compose a short MCP tool description from reusable guidance snippets."""
    parts = [summary, *notes]
    return " ".join(part for part in parts if part)


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


def payload_list(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize list payloads so MCP callers can omit optional arrays."""
    return items or []


def has_layout_ui_args(ui_args: dict[str, Any] | None) -> bool:
    """Detect layout-oriented widget UI args that need the layout tool instead."""
    if not isinstance(ui_args, dict):
        return False

    return any(
        key in ui_args
        for key in {
            "x",
            "y",
            "w",
            "h",
            "min_w",
            "min_h",
            "max_w",
            "max_h",
            "minW",
            "minH",
            "maxW",
            "maxH",
            "grid_data",
            "gridData",
            "inner_tab",
            "innerTab",
        }
    )


def is_generative_only_widget(widget_id: str) -> bool:
    """Return whether the widget must be created through add_generative_widget."""
    return widget_id == "rich_note"


def invalid_request(command: str, message: str) -> ToolResponse:
    """Build a standard invalid-request tool response."""
    return {
        "ok": False,
        "command": command,
        "request_id": None,
        "message": message,
        "data": None,
        "error": {
            "code": "invalid_request",
            "message": message,
            "details": None,
            "retryable": False,
        },
    }


def validate_add_generative_widget_request(
    *,
    widget_type: str,
    data: list[dict[str, Any]] | str | None,
    chart_params: dict[str, Any] | None,
) -> str | None:
    """Validate widget-type-specific generative widget payload requirements."""
    if widget_type in {"note", "html"}:
        if not isinstance(data, str):
            return (
                f"add_generative_widget with widget_type='{widget_type}' "
                "requires string data."
            )
        return None

    if not isinstance(data, list):
        return (
            f"add_generative_widget with widget_type='{widget_type}' "
            "requires data as list[dict]."
        )

    if widget_type != "chart":
        return None

    if not isinstance(chart_params, dict):
        return (
            "add_generative_widget with widget_type='chart' requires chart_params "
            "with chartType, xKey, and non-empty yKey."
        )

    y_key = chart_params.get("yKey")
    if (
        not isinstance(chart_params.get("chartType"), str)
        or not isinstance(chart_params.get("xKey"), str)
        or not isinstance(y_key, list)
        or not y_key
        or not all(isinstance(item, str) for item in y_key)
    ):
        return (
            "add_generative_widget with widget_type='chart' requires chart_params "
            "with chartType, xKey, and non-empty yKey."
        )

    return None


def data_source_payloads(items: list[WidgetDataRequest]) -> list[dict[str, Any]]:
    """Translate MCP-facing widget data items into the browser command shape."""
    return [
        {
            "origin": item.origin,
            "id": item.widget_id,
            "input_args": item.data_args,
            "widget_uuid": item.widget_uuid,
            "ssm_request": item.ssm_request,
        }
        for item in items
    ]


def param_options_payloads(items: list[ParamOptionsRequest]) -> list[dict[str, Any]]:
    """Translate MCP-facing option-query items into the browser command shape."""
    return [
        {
            "origin": item.origin,
            "id": item.widget_id,
            "param": item.param_name,
            "options_endpoint_input_args": item.data_args,
        }
        for item in items
    ]


def create_mcp_server(state: BridgeSessionManager) -> FastMCP:
    """Create the Workspace MCP server with a flat v1 tool list."""
    server = FastMCP(
        name="OpenBB Workspace MCP",
        instructions=SERVER_INSTRUCTIONS,
    )

    @server.prompt(
        name="workspace_tool_usage",
        description="Generic guidance for using the OpenBB Workspace MCP tool surface.",
    )
    def workspace_tool_usage() -> list[dict[str, str]]:
        """Return a compact, generic usage prompt for MCP agents."""
        return [{"role": "user", "content": SERVER_INSTRUCTIONS}]

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
        description=describe_tool(
            "Request a fresh OpenBB Workspace snapshot from the connected browser.",
            "Call this first when you need current dashboard state, dashboard identifiers across the workspace, or skill identifiers.",
            "The snapshot is intentionally compact: use list_available_widgets, get_widget_schema, and read_dashboard for deeper follow-up inspection.",
            "dashboard_composition exposes deterministic tabs, layout coordinates, and groups for the current dashboard.",
        )
    )
    async def get_workspace_snapshot(
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Fetch the current workspace snapshot from the connected browser."""
        _ = wait_for_previous
        return await run({"command": "get_workspace_snapshot"})

    @server.tool(
        description=describe_tool(
            "Fetch current data for one or more Workspace data sources.",
            DATA_SOURCE_SHAPE,
            "Only use this after selecting an exact widget identity and explicit data_args.",
        )
    )
    async def get_widget_data(
        data_sources: list[WidgetDataRequest],
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Fetch widget data using the same browser-side path Ada uses."""
        _ = wait_for_previous
        return await run(
            GetWidgetDataCommand(
                command="get_widget_data",
                data_sources=data_source_payloads(data_sources),
            )
        )

    @server.tool(
        description=describe_tool(
            "List widgets available to the current Workspace session.",
            "Returns deterministic widget identities for later get_widget_schema and create_widget calls.",
            "Generative-only note widgets such as rich_note are intentionally excluded; use add_generative_widget for those.",
            "Widgets that still require runtime-only bootstrap are also excluded until their plain create contract is deterministic.",
        )
    )
    async def list_available_widgets(
        origin: str | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """List widgets that can be created in the current Workspace session."""
        _ = wait_for_previous
        return await run(
            ListAvailableWidgetsCommand(
                command="list_available_widgets",
                origin=origin,
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
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Fetch one deterministic widget schema from the Workspace widget library."""
        _ = wait_for_previous
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
        param_options_queries: list[ParamOptionsRequest],
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Fetch parameter options from the browser bridge."""
        _ = wait_for_previous
        return await run(
            GetParamOptionsCommand(
                command="get_params_options",
                param_options_queries=param_options_payloads(param_options_queries),
            )
        )

    @server.tool(
        description=describe_tool(
            "Create one dashboard in the local Workspace session.",
            "Returns the new dashboard_id.",
            "By default the browser activates the new dashboard route.",
        )
    )
    async def create_dashboard(
        name: str,
        dashboard_id: str | None = None,
        activate: bool = True,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Create a dashboard for deterministic authoring flows."""
        _ = wait_for_previous
        return await run(
            CreateDashboardCommand(
                command="create_dashboard",
                name=name,
                dashboard_id=dashboard_id,
                activate=activate,
            )
        )

    @server.tool(
        description=describe_tool(
            "Update light metadata for one dashboard.",
            "Currently supports dashboard rename via name.",
        )
    )
    async def update_dashboard(
        dashboard_id: str,
        name: str | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Update light dashboard metadata."""
        _ = wait_for_previous
        if name is None:
            return invalid_request(
                "update_dashboard",
                "update_dashboard currently requires name.",
            )
        return await run(
            UpdateDashboardCommand(
                command="update_dashboard",
                dashboard_id=dashboard_id,
                name=name,
            )
        )

    @server.tool(
        description=describe_tool(
            "Read one dashboard's deterministic composition.",
            "Returns tabs, widget membership, layout coordinates, and groups for the target dashboard.",
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
        )
    )
    async def read_dashboard(
        dashboard_id: str | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Read one dashboard's deterministic composition."""
        _ = wait_for_previous
        return await run(
            ReadDashboardCommand(
                command="read_dashboard",
                dashboard_id=dashboard_id,
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
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Load one widget's current payload from Workspace.

        ``widget_uuid`` is the canonical instance identifier. ``widget_id`` is
        accepted as a fallback alias for callers that only know the widget type
        identifier and need the browser bridge to resolve the active instance.
        """
        _ = wait_for_previous
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
        backend_name: str | None = None,
        data_args: dict[str, Any] | None = None,
        ui_args: dict[str, Any] | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Create a new Workspace widget."""
        _ = wait_for_previous
        resolved_origin = origin or backend_name
        if not resolved_origin or not widget_id:
            return invalid_request(
                "create_widget",
                "create_widget requires origin from list_available_widgets and widget_id.",
            )
        if origin and backend_name and origin != backend_name:
            return invalid_request(
                "create_widget",
                "create_widget received conflicting origin and backend_name values. Pass one catalog identity only.",
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
                backend_name=resolved_origin,
                widget_id=widget_id,
                config=widget_config(data_args=data_args, ui_args=ui_args),
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
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Update an existing Workspace widget."""
        _ = wait_for_previous
        if has_layout_ui_args(ui_args):
            return invalid_request(
                "update_widget",
                "update_widget only supports widget-instance config changes. "
                "Use update_dashboard_layout for x, y, w, h, gridData, or tab_id.",
            )
        return await run(
            UpdateWidgetCommand(
                command="update_widget",
                dashboard_id=dashboard_id,
                widget_uuid=widget_uuid,
                widget_id=widget_id,
                config=required_widget_config(data_args=data_args, ui_args=ui_args),
            )
        )

    @server.tool(
        description=describe_tool(
            "Move or resize one widget in dashboard layout space.",
            "Requires x, y, w, and h. Use tab_id from read_dashboard or get_workspace_snapshot.dashboard_composition when moving across tabs.",
            "The layout grid is 40 columns wide: full width is w=40, half width is w=20, one quarter is w=10. If a navigation_bar is present, first content usually starts at y=2.",
            WIDGET_INSTANCE_GUIDANCE,
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
        )
    )
    async def update_dashboard_layout(
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
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Move or resize one widget in dashboard layout space."""
        _ = wait_for_previous
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
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Delete a Workspace widget."""
        _ = wait_for_previous
        return await run(
            DeleteWidgetCommand(
                command="delete_widget",
                dashboard_id=dashboard_id,
                widget_uuid=widget_uuid,
                widget_id=widget_id,
            )
        )

    @server.tool(
        description=describe_tool(
            "Create or mutate the Workspace navigation bar.",
            "Requires operation from {create, add_tabs, remove_tabs, rename_tabs}.",
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
            NAVIGATION_BAR_GUIDANCE,
        )
    )
    async def manage_navigation_bar(
        operation: str,
        dashboard_id: str | None = None,
        tabs: list[dict[str, Any]] | None = None,
        rename_map: dict[str, str] | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Create tabs or update navigation tab metadata."""
        _ = wait_for_previous
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
        return await run(
            ManageNavigationBarCommand(
                command="manage_navigation_bar",
                dashboard_id=dashboard_id,
                operation=cast(Any, operation),
                tabs=tabs or [],
                rename_map=rename_map or {},
            )
        )

    @server.tool(
        description=describe_tool(
            "Create a generated note, table, chart, or HTML widget.",
            "Requires widget_type from {note, table, chart, html}.",
            GENERATIVE_WIDGET_GUIDANCE,
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
        )
    )
    async def add_generative_widget(
        widget_type: str,
        dashboard_id: str | None = None,
        data: list[dict[str, Any]] | str | None = None,
        name: str | None = None,
        description: str | None = None,
        chart_params: dict[str, Any] | None = None,
        inner_tab: str | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Create a generative widget from inline content."""
        _ = wait_for_previous
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

    @server.tool(
        description=describe_tool(
            "Assign tasks to configured external Workspace agents.",
            "Use task_requests items shaped like {id, description, assigned_holder_url, assigned_agent_id}.",
        )
    )
    async def assign_tasks_to_agents(
        task_requests: list[dict[str, Any]],
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Delegate work to Workspace agents through the browser bridge."""
        _ = wait_for_previous
        return await run(
            AssignTasksToAgentsCommand(
                command="assign_tasks_to_agents",
                task_requests=payload_list(task_requests),
            )
        )

    @server.tool(
        description=describe_tool(
            "Execute one Workspace-connected MCP tool.",
            "Requires server_id, tool_name, and optional parameters.",
        )
    )
    async def execute_agent_tool(
        server_id: str,
        tool_name: str,
        parameters: dict[str, Any] | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Execute one MCP tool via Workspace's existing MCP executor."""
        _ = wait_for_previous
        return await run(
            ExecuteAgentToolCommand(
                command="execute_agent_tool",
                server_id=server_id,
                tool_name=tool_name,
                parameters=parameters or {},
            )
        )

    @server.tool(
        description=describe_tool(
            "Load one skill body from the Workspace skill library.",
            "Pass the exact skill slug from the latest workspace snapshot.",
        )
    )
    async def get_skill_content(
        slug: str,
        reason: str | None = None,
        wait_for_previous: bool | None = None,
    ) -> ToolResponse:
        """Load one skill from Workspace's skill library."""
        _ = wait_for_previous
        return await run(
            GetSkillContentCommand(
                command="get_skill_content",
                slug=slug,
                reason=reason,
            )
        )

    return server
