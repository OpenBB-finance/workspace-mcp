"""FastMCP tool surface for the Workspace sidecar."""

import json
from typing import Any, cast

from fastmcp import FastMCP
from pydantic import ValidationError

from workspace_mcp.models import (
    AddGenerativeWidgetCommand,
    AssignTasksToAgentsCommand,
    BackendEndpointHeader,
    CreateWidgetCommand,
    DeleteWidgetCommand,
    GetParamOptionsCommand,
    GetSkillContentCommand,
    GetWidgetDataCommand,
    GetWidgetSchemaCommand,
    ListAvailableWidgetsCommand,
    ManageAppsCommand,
    ManageBackendsCommand,
    ManageDashboardCommand,
    ManageNavigationBarCommand,
    NavigateWorkspaceCommand,
    ParamOptionsRequest,
    ReadWidgetCommand,
    UpdateDashboardLayoutCommand,
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
    "list_available_widgets. Pass data_args_json and ui_args_json as JSON "
    "object strings when config values are needed."
)
DATA_SOURCE_SHAPE = (
    "Pass origin, widget_id, and data_args_json for one data source. "
    "data_args_json and ssm_request_json must be JSON object strings."
)
PARAM_OPTIONS_SHAPE = (
    "Pass origin, widget_id, param_name, and optional data_args_json for one "
    "parameter option query. Only call get_params_options after get_widget_schema "
    "shows the exact param has requires_options_lookup=true. Use the exact "
    "paramName from the schema as param_name. data_args_json must be a JSON "
    "object string with the values required by options_lookup_params when present."
)
GENERATIVE_WIDGET_GUIDANCE = (
    "For add_generative_widget: note and html require data_json as the raw text "
    "or HTML content string; JSON string literals are also accepted. table requires "
    "data_json as a JSON array of objects. chart requires data_json as a JSON "
    "array of objects plus chart_params_json as a JSON object with chartType, "
    "xKey, and non-empty yKey. "
    "Use widget_type='note' for rich text notes such as rich_note. "
    "The response includes widget_uuid; use that UUID for layout changes. "
    "The inner_tab argument only places the new widget on an existing navigation tab; "
    "it does not create a tab. To put a generated widget on a new tab, first call "
    'manage_navigation_bar operation="add_tabs" with tabs_json such as [{"name":"AAPL Analysis"}], '
    "then navigate_workspace to the generated slug tab_id such as aapl-analysis, "
    "then call add_generative_widget without inner_tab so it lands on the active tab."
)
WIDGET_INSTANCE_GUIDANCE = (
    "Prefer widget_uuid for read, update, and delete. widget_id is only a fallback "
    "when exactly one matching widget instance exists on the target dashboard. "
    "Never use a widget title or generic widget type such as rich_note as a layout "
    "identifier."
)
DASHBOARD_TARGETING_GUIDANCE = (
    "Resolve dashboard_id from current_dashboard_uuid before each write. Every "
    "successful command result includes session_context.current_dashboard_uuid "
    "(and current_tab_id) — reuse that from the previous response instead of "
    "calling get_workspace_snapshot again. Use get_workspace_snapshot only on "
    "the first call, or after a navigation step that may have invalidated the "
    "tracked context. Never match dashboards by name: duplicates with identical "
    "names are common. \"This dashboard\" means the current route; resolve via "
    "current_dashboard_uuid, not title. Omitting dashboard_id also targets the "
    "current route, but do not send placeholder strings such as active_dashboard, "
    "current_dashboard, null, or undefined."
)
EXISTING_DASHBOARD_GUIDANCE = (
    "These tools operate on an existing dashboard only. They do not create dashboards."
)
CREATE_DASHBOARD_GUIDANCE = (
    "Use manage_dashboard with operation='create' to create a dashboard first. "
    "By default it activates the new dashboard route so follow-up snapshot and "
    "widget commands target it."
)
LAYOUT_GUIDANCE = (
    "Visible placement is controlled by dashboard composition, not update_widget. "
    "Use manage_dashboard operation='read' or get_workspace_snapshot.dashboard_composition "
    "to inspect tabs and layout, then use update_widget_layout for x, y, w, h, and tab_id. "
    "The grid is 40 columns wide: full width is w=40, half width is w=20, one quarter "
    "is w=10. Typical minimums are about min_w=8 and min_h=4. If a navigation_bar is "
    "present it usually occupies y=0 with h=2, so the first content row usually starts "
    "at y=2."
)
NAVIGATION_BAR_GUIDANCE = (
    "manage_navigation_bar manages the navigation_bar widget inside an existing dashboard. "
    "If the dashboard does not already have a navigation_bar widget, call create first. "
    "Its create operation creates or initializes navigation tabs on that dashboard; it does not create a dashboard. "
    "For create, add_tabs, and remove_tabs, tabs_json must be a JSON array of objects, "
    'for example [{"name":"AAPL Analysis"}]. Each object must use only the key name, not tab_id or tab_name. '
    'Do not pass a JSON array of strings such as ["AAPL Analysis"].'
)
DISCOVERY_WORKFLOW = (
    "Recommended workflow: call get_workspace_snapshot first, manage_dashboard "
    "with operation='create' when you need a fresh dashboard, call "
    "list_available_widgets to enumerate candidate widgets, call "
    "get_widget_schema for the exact widget contract, call "
    "get_params_options when a schema field returns requires_options_lookup=true, then call "
    "create_widget with explicit dashboard_id, origin, widget_id, data_args_json, "
    "and ui_args_json. list_available_widgets only returns the deterministic plain-create "
    "subset; widgets that still need runtime-only bootstrap are intentionally "
    "excluded. Do not use create_widget for rich_note; use add_generative_widget "
    "with widget_type='note'. Use manage_dashboard operation='read' or "
    "get_workspace_snapshot.dashboard_composition "
    "to inspect visible layout and update_widget_layout to move or resize "
    "widgets. When asked to put content on a new tab, create the tab first with "
    "manage_navigation_bar add_tabs using tabs_json objects with only name, then "
    "navigate_workspace to the generated slug tab_id, then create the widget without "
    "inner_tab or move an existing widget with update_widget_layout. Do not assume "
    "add_generative_widget inner_tab creates the tab."
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


class JsonArgumentError(ValueError):
    """Invalid JSON string supplied to a flat MCP tool argument."""

    def __init__(self, response: ToolResponse):
        super().__init__(response["message"])
        self.response = response


def parse_json_list(
    command: str,
    field_name: str,
    raw_value: str | None,
) -> list[dict[str, Any]]:
    """Parse a JSON string argument that must contain a list of objects."""
    if raw_value is None:
        return []
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise JsonArgumentError(
            invalid_request(
                command,
                f"{command} requires {field_name} to be valid JSON: {error.msg}.",
            )
        )
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise JsonArgumentError(
            invalid_request(
                command,
                f"{command} requires {field_name} as a JSON array of objects.",
            )
        )
    return value


def parse_json_dict(
    command: str,
    field_name: str,
    raw_value: str | None,
) -> dict[str, Any]:
    """Parse a JSON string argument that must contain an object."""
    if raw_value is None:
        return {}
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise JsonArgumentError(
            invalid_request(
                command,
                f"{command} requires {field_name} to be valid JSON: {error.msg}.",
            )
        )
    if not isinstance(value, dict):
        raise JsonArgumentError(
            invalid_request(
                command,
                f"{command} requires {field_name} as a JSON object.",
            )
        )
    return value


def validate_navigation_tabs(
    operation: str,
    tabs: list[dict[str, Any]],
) -> ToolResponse | None:
    """Validate navigation-tab payloads before forwarding to the browser."""
    if operation not in {"create", "add_tabs", "remove_tabs"}:
        return None

    for item in tabs:
        if "tab_id" in item or "tab_name" in item:
            return invalid_request(
                "manage_navigation_bar",
                "manage_navigation_bar tabs_json items must not include tab_id or tab_name; "
                'use only {"name":"AAPL Analysis"}. The tab_id is generated as the slug of name.',
            )
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            return invalid_request(
                "manage_navigation_bar",
                "manage_navigation_bar tabs_json items must be objects with a non-empty string 'name' field, "
                'for example [{"name":"AAPL Analysis"}]. Do not use tab_id/tab_name keys.',
            )

    return None


def parse_json_value(
    command: str,
    field_name: str,
    raw_value: str | None,
) -> Any:
    """Parse a JSON string argument into any JSON value."""
    if raw_value is None:
        return None
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise JsonArgumentError(
            invalid_request(
                command,
                f"{command} requires {field_name} to be valid JSON: {error.msg}.",
            )
        )


def parse_generative_data(widget_type: str, raw_value: str | None) -> Any:
    """Parse data_json, accepting plain strings for text-like widgets."""
    try:
        return parse_json_value("add_generative_widget", "data_json", raw_value)
    except JsonArgumentError as error:
        if widget_type in {"note", "html"} and raw_value is not None:
            return raw_value
        raise error


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


def session_context_prompt_content(state: BridgeSessionManager) -> str:
    """Describe the currently tracked dashboard and tab session context."""
    session = state.get_session_context()
    if session is None:
        return "No Workspace browser session context is currently available."

    dashboard_id = session.current_dashboard_id or "none"
    tab_id = session.current_tab_id or "none"
    return (
        "Current Workspace browser session context: "
        f"current_dashboard_id={dashboard_id}; "
        f"current_tab_id={tab_id}."
    )


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

    @server.tool(
        description=describe_tool(
            "Request a fresh OpenBB Workspace snapshot from the connected browser.",
            "Call this first when you need current dashboard state, dashboard identifiers across the workspace, or skill identifiers.",
            "The snapshot is intentionally compact: use list_available_widgets, get_widget_schema, and manage_dashboard for deeper follow-up inspection.",
            "dashboard_composition exposes deterministic tabs, layout coordinates, and groups for the current dashboard.",
        )
    )
    async def get_workspace_snapshot() -> ToolResponse:
        """Fetch the current workspace snapshot from the connected browser."""
        return await run({"command": "get_workspace_snapshot"})

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
        data_args_json: str | None = None,
        widget_uuid: str | None = None,
        ssm_request_json: str | None = None,
    ) -> ToolResponse:
        """Fetch widget data using the same browser-side path Ada uses."""
        try:
            data_args = parse_json_dict(
                "get_widget_data", "data_args_json", data_args_json
            )
            ssm_request = parse_json_dict(
                "get_widget_data", "ssm_request_json", ssm_request_json
            )
        except JsonArgumentError as error:
            return error.response
        return await run(
            GetWidgetDataCommand(
                command="get_widget_data",
                data_sources=data_source_payloads(
                    [
                        WidgetDataRequest(
                            origin=origin,
                            widget_id=widget_id,
                            data_args=data_args,
                            widget_uuid=widget_uuid,
                            ssm_request=ssm_request or None,
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
        data_args_json: str | None = None,
    ) -> ToolResponse:
        """Fetch parameter options from the browser bridge."""
        try:
            data_args = parse_json_dict(
                "get_params_options", "data_args_json", data_args_json
            )
        except JsonArgumentError as error:
            return error.response
        return await run(
            GetParamOptionsCommand(
                command="get_params_options",
                param_options_queries=param_options_payloads(
                    [
                        ParamOptionsRequest(
                            origin=origin,
                            widget_id=widget_id,
                            param_name=param_name,
                            data_args=data_args,
                        )
                    ]
                ),
            )
        )

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
        data_args_json: str | None = None,
        ui_args_json: str | None = None,
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
        try:
            data_args = parse_json_dict(
                "create_widget", "data_args_json", data_args_json
            )
            ui_args = parse_json_dict("create_widget", "ui_args_json", ui_args_json)
        except JsonArgumentError as error:
            return error.response
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
        data_args_json: str | None = None,
        ui_args_json: str | None = None,
    ) -> ToolResponse:
        """Update an existing Workspace widget."""
        try:
            data_args = parse_json_dict(
                "update_widget", "data_args_json", data_args_json
            )
            ui_args = parse_json_dict("update_widget", "ui_args_json", ui_args_json)
        except JsonArgumentError as error:
            return error.response
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

    @server.tool(
        description=describe_tool(
            "Create or mutate the Workspace navigation bar.",
            "Requires operation from {create, add_tabs, remove_tabs, rename_tabs}.",
            'For add_tabs, pass tabs_json as a JSON array of objects, for example [{"name":"AAPL Analysis"}].',
            'The only tab object field for create/add/remove is name; do not send tab_id or tab_name. The tab_id is generated as the slug of name.',
            'Do not pass tabs_json as ["AAPL Analysis"]; string arrays are rejected.',
            'After add_tabs, navigate to the generated slug tab_id, e.g. AAPL Analysis -> aapl-analysis, before creating content for that tab.',
            'For rename_tabs, pass rename_map_json as a JSON object, for example {"old-tab-id":"New Name"}.',
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
            NAVIGATION_BAR_GUIDANCE,
        )
    )
    async def manage_navigation_bar(
        operation: str,
        dashboard_id: str | None = None,
        tabs_json: str | None = None,
        rename_map_json: str | None = None,
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
        try:
            tabs = parse_json_list("manage_navigation_bar", "tabs_json", tabs_json)
            rename_map = parse_json_dict(
                "manage_navigation_bar", "rename_map_json", rename_map_json
            )
        except JsonArgumentError as error:
            return error.response
        if operation in {"create", "add_tabs", "remove_tabs"} and not tabs:
            return invalid_request(
                "manage_navigation_bar",
                f"manage_navigation_bar operation='{operation}' requires tabs_json.",
            )
        tab_error = validate_navigation_tabs(operation, tabs)
        if tab_error:
            return tab_error
        if operation == "rename_tabs" and not rename_map:
            return invalid_request(
                "manage_navigation_bar",
                "manage_navigation_bar operation='rename_tabs' requires rename_map_json.",
            )
        return await run(
            ManageNavigationBarCommand(
                command="manage_navigation_bar",
                dashboard_id=dashboard_id,
                operation=cast(Any, operation),
                tabs=tabs,
                rename_map=cast(dict[str, str], rename_map),
            )
        )

    @server.tool(
        description=describe_tool(
            "Create a generated note, table, chart, or HTML widget.",
            "Requires widget_type from {note, table, chart, html}.",
            "inner_tab targets an existing navigation tab only; it does not create a new tab.",
            'For a new tab workflow, call manage_navigation_bar operation="add_tabs" with tabs_json like [{"name":"AAPL Analysis"}], navigate_workspace to the generated slug tab_id, then call add_generative_widget without inner_tab.',
            GENERATIVE_WIDGET_GUIDANCE,
            DASHBOARD_TARGETING_GUIDANCE,
            EXISTING_DASHBOARD_GUIDANCE,
        )
    )
    async def add_generative_widget(
        widget_type: str,
        dashboard_id: str | None = None,
        data_json: str | None = None,
        name: str | None = None,
        description: str | None = None,
        chart_params_json: str | None = None,
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
        try:
            data = parse_generative_data(widget_type, data_json)
            chart_params = parse_json_dict(
                "add_generative_widget", "chart_params_json", chart_params_json
            )
        except JsonArgumentError as error:
            return error.response
        payload_error = validate_add_generative_widget_request(
            widget_type=widget_type,
            data=cast(list[dict[str, Any]] | str | None, data),
            chart_params=chart_params or None,
        )
        if payload_error:
            return invalid_request("add_generative_widget", payload_error)
        return await run(
            AddGenerativeWidgetCommand(
                command="add_generative_widget",
                dashboard_id=dashboard_id,
                widget_type=cast(Any, widget_type),
                data=cast(list[dict[str, Any]] | str | None, data),
                name=name,
                description=description,
                chart_params=chart_params or None,
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
        task_requests_json: str,
    ) -> ToolResponse:
        """Delegate work to Workspace agents through the browser bridge."""
        try:
            task_requests = parse_json_list(
                "assign_tasks_to_agents", "task_requests_json", task_requests_json
            )
        except JsonArgumentError as error:
            return error.response
        return await run(
            AssignTasksToAgentsCommand(
                command="assign_tasks_to_agents",
                task_requests=payload_list(task_requests),
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
    ) -> ToolResponse:
        """Load one skill from Workspace's skill library."""
        return await run(
            GetSkillContentCommand(
                command="get_skill_content",
                slug=slug,
                reason=reason,
            )
        )

    @server.tool(
        description=describe_tool(
            "Manage Workspace data backends (the connections that power widgets).",
            "Requires operation from {list, add, update, refresh, remove}.",
            "For list, returns each backend with id, name, url, status, and widget/app/agent counts.",
            "For add, requires name and url. Optional endpoint_headers_json is a JSON array of "
            '{"key", "value", "location"} where location is "headers" (default) or "query". '
            "validate_widgets defaults to true and surfaces a warning if widgets fail to load.",
            "For update, requires backend_id and at least one of name, url, or endpoint_headers_json.",
            "For refresh, requires backend_id; re-fetches widgets and templates from the backend URL.",
            "For remove, requires backend_id.",
        )
    )
    async def manage_backends(
        operation: str,
        backend_id: str | None = None,
        name: str | None = None,
        url: str | None = None,
        endpoint_headers_json: str | None = None,
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

        endpoint_headers: list[BackendEndpointHeader] | None = None
        if endpoint_headers_json is not None:
            try:
                raw_headers = parse_json_list(
                    "manage_backends", "endpoint_headers_json", endpoint_headers_json
                )
            except JsonArgumentError as error:
                return error.response
            try:
                endpoint_headers = [
                    BackendEndpointHeader.model_validate(item) for item in raw_headers
                ]
            except ValidationError:
                return invalid_request(
                    "manage_backends",
                    "manage_backends endpoint_headers_json items must be objects with "
                    "string 'key' and 'value' fields and optional 'location' as 'headers' or 'query'.",
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
                    "name, url, endpoint_headers_json, or is_openbb_platform.",
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

    return server
