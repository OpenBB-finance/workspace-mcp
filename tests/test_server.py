"""Server metadata tests for the Workspace MCP tool surface."""

import json
from typing import cast

import pytest

from workspace_mcp.models import (
    AddGenerativeWidgetCommand,
    CreateWidgetCommand,
    GetWidgetSchemaCommand,
    ManageDashboardCommand,
    ManageNavigationBarCommand,
    NavigateWorkspaceCommand,
    ParamOptionsRequest,
    UpdateDashboardLayoutCommand,
    UpdateWidgetCommand,
    WidgetDataRequest,
    WorkspaceCommand,
    WorkspaceCommandResult,
    WorkspaceWidgetConfig,
    workspace_command_adapter,
)
from workspace_mcp.server import (
    SERVER_INSTRUCTIONS,
    create_mcp_server,
    data_source_payloads,
    invalid_request,
    is_generative_only_widget,
    param_options_payloads,
    validate_add_generative_widget_request,
)
from workspace_mcp.state import BridgeSessionManager


class RecordingBridgeState:
    """Small bridge double that records commands sent by tool handlers."""

    def __init__(self) -> None:
        self.commands: list[WorkspaceCommand] = []

    async def execute_command(
        self, command: WorkspaceCommand | dict[str, object]
    ) -> WorkspaceCommandResult:
        if isinstance(command, dict):
            command = workspace_command_adapter.validate_python(command)
        self.commands.append(command)
        return WorkspaceCommandResult(
            ok=True,
            command=command.command,
            request_id=command.request_id,
            message="ok",
        )


@pytest.mark.asyncio
async def test_workspace_tool_usage_prompt_is_registered() -> None:
    """The server should publish a generic usage prompt for MCP agents."""
    server = create_mcp_server(
        BridgeSessionManager(
            base_url="http://127.0.0.1:8787",
            websocket_path="/bridge/ws",
            command_timeout_seconds=1,
        )
    )

    prompts = await server.list_prompts()

    assert {prompt.name for prompt in prompts} == {
        "workspace_tool_usage",
        "workspace_session_context",
    }
    assert prompts[0].description == (
        "Generic guidance for using the OpenBB Workspace MCP tool surface."
    )
    assert "get_workspace_snapshot" in SERVER_INSTRUCTIONS
    assert "Pass origin, widget_id, and data_args" in SERVER_INSTRUCTIONS
    assert "Do not use create_widget for rich_note" in SERVER_INSTRUCTIONS
    assert "The grid is 40 columns wide" in SERVER_INSTRUCTIONS
    assert "grid_data defaults and min/max layout constraints" in SERVER_INSTRUCTIONS
    assert "deterministic plain-create subset" in SERVER_INSTRUCTIONS
    assert "requires_options_lookup=true" in SERVER_INSTRUCTIONS
    assert "exact paramName from the schema as param_name" in SERVER_INSTRUCTIONS
    assert "options_lookup_params" in SERVER_INSTRUCTIONS
    assert "dashboard_id, dashboard_composition, and skills" in SERVER_INSTRUCTIONS
    assert "data_args must be an object" in SERVER_INSTRUCTIONS
    assert "data as the raw text" in SERVER_INSTRUCTIONS
    assert "pass origin as the exact catalog value returned by list_available_widgets" in SERVER_INSTRUCTIONS
    assert "use that UUID for layout changes" in SERVER_INSTRUCTIONS
    assert "Never use a widget title or generic widget type" in SERVER_INSTRUCTIONS


@pytest.mark.asyncio
async def test_workspace_tool_surface_excludes_removed_noop_fields() -> None:
    """The public MCP schema should not expose removed pass-through fields."""
    server = create_mcp_server(
        BridgeSessionManager(
            base_url="http://127.0.0.1:8787",
            websocket_path="/bridge/ws",
            command_timeout_seconds=1,
        )
    )

    tools = await server.list_tools()
    tool_names = {tool.name for tool in tools}

    assert "execute_agent_tool" not in tool_names
    assert "wait_for_previous" not in {
        name
        for tool in tools
        for name in (tool.parameters.get("properties") or {})
    }
    assert {"manage_dashboard", "navigate_workspace", "update_widget_layout"}.issubset(
        tool_names
    )
    assert {"create_dashboard", "read_dashboard", "update_dashboard"}.isdisjoint(
        tool_names
    )
    assert {"navigate_to_dashboard", "switch_tab", "update_dashboard_layout"}.isdisjoint(
        tool_names
    )


@pytest.mark.asyncio
async def test_manage_dashboard_sends_settled_bridge_command() -> None:
    """The grouped dashboard MCP tool should not emit removed bridge commands."""
    state = RecordingBridgeState()
    server = create_mcp_server(cast(BridgeSessionManager, state))

    result = await server.call_tool("manage_dashboard", {"operation": "read"})

    assert result.structured_content == {
        "ok": True,
        "command": "manage_dashboard",
        "request_id": None,
        "message": "ok",
        "data": None,
        "error": None,
    }
    assert len(state.commands) == 1
    command = state.commands[0]
    assert isinstance(command, ManageDashboardCommand)
    assert command.command == "manage_dashboard"
    assert command.operation == "read"


@pytest.mark.asyncio
async def test_navigate_workspace_sends_settled_bridge_command() -> None:
    """The grouped navigation MCP tool should not emit removed bridge commands."""
    state = RecordingBridgeState()
    server = create_mcp_server(cast(BridgeSessionManager, state))

    result = await server.call_tool(
        "navigate_workspace",
        {"operation": "tab", "tab_id": "tab-news"},
    )

    assert result.structured_content == {
        "ok": True,
        "command": "navigate_workspace",
        "request_id": None,
        "message": "ok",
        "data": None,
        "error": None,
    }
    assert len(state.commands) == 1
    command = state.commands[0]
    assert isinstance(command, NavigateWorkspaceCommand)
    assert command.command == "navigate_workspace"
    assert command.operation == "tab"
    assert command.tab_id == "tab-news"


@pytest.mark.asyncio
async def test_text_generative_widgets_accept_raw_string_data() -> None:
    """Notes and HTML widgets should accept plain string content via the typed `data` param."""
    state = RecordingBridgeState()
    server = create_mcp_server(cast(BridgeSessionManager, state))

    result = await server.call_tool(
        "add_generative_widget",
        {
            "widget_type": "note",
            "name": "Briefing",
            "data": "# Briefing\n\nRaw markdown body.",
        },
    )

    assert result.structured_content == {
        "ok": True,
        "command": "add_generative_widget",
        "request_id": None,
        "message": "ok",
        "data": None,
        "error": None,
    }
    assert len(state.commands) == 1
    command = state.commands[0]
    assert isinstance(command, AddGenerativeWidgetCommand)
    assert command.data == "# Briefing\n\nRaw markdown body."


def test_get_widget_schema_command_accepts_missing_origin_for_tool_error() -> None:
    """Missing origin should reach the tool handler so it can fail explicitly."""
    command = GetWidgetSchemaCommand(command="get_widget_schema", widget_id="price")

    assert command.origin is None


def test_data_source_payloads_translate_snapshot_names() -> None:
    """The MCP layer should accept snapshot-aligned widget-data fields."""
    payloads = data_source_payloads(
        [
            WidgetDataRequest(
                origin="OpenBB Polymarket",
                widget_id="event_markets",
                data_args={"event_id": "158299"},
                widget_uuid="widget-1",
            )
        ]
    )

    assert payloads == [
        {
            "origin": "OpenBB Polymarket",
            "id": "event_markets",
            "input_args": {"event_id": "158299"},
            "widget_uuid": "widget-1",
            "ssm_request": None,
        }
    ]


def test_data_source_payloads_accept_backend_name_alias() -> None:
    """The MCP layer should accept backend_name as an alias for origin."""
    payloads = data_source_payloads(
        [
            WidgetDataRequest.model_validate(
                {
                    "backend_name": "OpenBB Polymarket",
                    "widget_id": "event_markets",
                    "data_args": {"event_id": "158299"},
                }
            )
        ]
    )

    assert payloads == [
        {
            "origin": "OpenBB Polymarket",
            "id": "event_markets",
            "input_args": {"event_id": "158299"},
            "widget_uuid": None,
            "ssm_request": None,
        }
    ]


def test_data_source_payloads_accept_params_alias() -> None:
    """The MCP layer should accept params as an alias for data_args."""
    payloads = data_source_payloads(
        [
            WidgetDataRequest.model_validate(
                {
                    "origin": "OpenBB Polymarket",
                    "widget_id": "search_events",
                    "params": {"query": "Iran"},
                }
            )
        ]
    )

    assert payloads == [
        {
            "origin": "OpenBB Polymarket",
            "id": "search_events",
            "input_args": {"query": "Iran"},
            "widget_uuid": None,
            "ssm_request": None,
        }
    ]


def test_param_options_payloads_translate_snapshot_names() -> None:
    """The MCP layer should accept snapshot-aligned param-option fields."""
    payloads = param_options_payloads(
        [
            ParamOptionsRequest(
                origin="OpenBB Polymarket",
                widget_id="search_events",
                param_name="tag",
                data_args={"search": "iran"},
            )
        ]
    )

    assert payloads == [
        {
            "origin": "OpenBB Polymarket",
            "id": "search_events",
            "param": "tag",
            "options_endpoint_input_args": {"search": "iran"},
        }
    ]


def test_invalid_request_builds_standard_tool_error() -> None:
    """Invalid MCP inputs should produce a normal tool error payload."""
    response = invalid_request(
        "manage_navigation_bar",
        "manage_navigation_bar requires operation from {create, add_tabs, remove_tabs, rename_tabs}.",
    )

    assert response == {
        "ok": False,
        "command": "manage_navigation_bar",
        "request_id": None,
        "message": "manage_navigation_bar requires operation from {create, add_tabs, remove_tabs, rename_tabs}.",
        "data": None,
        "error": {
            "code": "invalid_request",
            "message": "manage_navigation_bar requires operation from {create, add_tabs, remove_tabs, rename_tabs}.",
            "details": None,
            "retryable": False,
        },
    }


def test_navigation_tab_input_rejects_tab_id_and_tab_name_extras() -> None:
    """NavigationTabInput should reject the common LLM mistake of sending tab_id."""
    from pydantic import ValidationError

    from workspace_mcp.models import NavigationTabInput

    with pytest.raises(ValidationError) as excinfo:
        NavigationTabInput.model_validate(
            {"tab_id": "aapl-analysis", "tab_name": "AAPL Analysis"}
        )

    error_text = str(excinfo.value)
    assert "tab_id" in error_text
    assert "tab_name" in error_text


def test_navigation_tab_input_rejects_blank_name() -> None:
    """NavigationTabInput should reject empty and whitespace-only names."""
    from pydantic import ValidationError

    from workspace_mcp.models import NavigationTabInput

    for blank in ("", "   "):
        with pytest.raises(ValidationError):
            NavigationTabInput.model_validate({"name": blank})


def test_navigation_tab_input_accepts_name_only() -> None:
    """NavigationTabInput should accept the documented {name} shape."""
    from workspace_mcp.models import NavigationTabInput

    tab = NavigationTabInput.model_validate({"name": "AAPL Analysis"})
    assert tab.model_dump() == {"name": "AAPL Analysis"}


def test_is_generative_only_widget_identifies_rich_note() -> None:
    """rich_note should stay on the generative widget path only."""
    assert is_generative_only_widget("rich_note") is True
    assert is_generative_only_widget("market_indices") is False


def test_param_options_payloads_accept_backend_name_alias() -> None:
    """The MCP layer should accept backend_name for param-option queries too."""
    payloads = param_options_payloads(
        [
            ParamOptionsRequest.model_validate(
                {
                    "backend_name": "OpenBB Polymarket",
                    "widget_id": "search_events",
                    "param_name": "tag",
                    "data_args": {"search": "iran"},
                }
            )
        ]
    )

    assert payloads == [
        {
            "origin": "OpenBB Polymarket",
            "id": "search_events",
            "param": "tag",
            "options_endpoint_input_args": {"search": "iran"},
        }
    ]


def test_param_options_payloads_accept_params_alias() -> None:
    """The MCP layer should accept params as an alias for option-query args."""
    payloads = param_options_payloads(
        [
            ParamOptionsRequest.model_validate(
                {
                    "origin": "OpenBB Polymarket",
                    "widget_id": "search_events",
                    "param_name": "tag",
                    "params": {"query": "Iran"},
                }
            )
        ]
    )

    assert payloads == [
        {
            "origin": "OpenBB Polymarket",
            "id": "search_events",
            "param": "tag",
            "options_endpoint_input_args": {"query": "Iran"},
        }
    ]


def test_dashboard_scoped_commands_accept_omitted_dashboard_id() -> None:
    """Current-route commands should allow omitted dashboard_id internally too."""
    create_command = CreateWidgetCommand(
        command="create_widget",
        backend_name="OpenBB Workspace",
        widget_id="rich_note",
    )
    update_command = UpdateWidgetCommand(
        command="update_widget",
        widget_uuid="widget-1",
        config=WorkspaceWidgetConfig(),
    )
    nav_command = ManageNavigationBarCommand(
        command="manage_navigation_bar",
        operation="create",
    )
    generative_command = AddGenerativeWidgetCommand(
        command="add_generative_widget",
        widget_type="note",
    )

    assert create_command.dashboard_id is None
    assert update_command.dashboard_id is None
    assert nav_command.dashboard_id is None
    assert generative_command.dashboard_id is None


def test_create_widget_command_accepts_origin_alias() -> None:
    """The MCP layer should accept origin for create-widget identity too."""
    command = CreateWidgetCommand.model_validate(
        {
            "command": "create_widget",
            "origin": "OpenBB Sandbox",
            "widget_id": "price_performance",
        }
    )

    assert command.backend_name == "OpenBB Sandbox"


@pytest.mark.parametrize("widget_type", ["note", "html"])
def test_generative_widget_validation_requires_string_for_text_widgets(
    widget_type: str,
) -> None:
    """Text-like generative widgets should reject non-string data."""
    message = validate_add_generative_widget_request(
        widget_type=widget_type,
        data=[{"body": "not allowed"}],
        chart_params=None,
    )

    assert message == (
        f"add_generative_widget with widget_type='{widget_type}' "
        "requires string data."
    )


def test_generative_widget_validation_requires_list_data_for_table() -> None:
    """Table widgets should reject string payloads."""
    message = validate_add_generative_widget_request(
        widget_type="table",
        data="not a table",
        chart_params=None,
    )

    assert message == (
        "add_generative_widget with widget_type='table' requires data as list[dict]."
    )


def test_generative_widget_validation_requires_chart_params_for_chart() -> None:
    """Chart widgets should reject incomplete chart configuration."""
    message = validate_add_generative_widget_request(
        widget_type="chart",
        data=[{"quarter": "Q1", "value": 1}],
        chart_params={"chartType": "bar", "xKey": "quarter"},
    )

    assert message == (
        "add_generative_widget with widget_type='chart' requires chart_params "
        "with chartType, xKey, and non-empty yKey."
    )


def test_generative_widget_validation_accepts_valid_chart_payload() -> None:
    """Valid chart payloads should pass validation."""
    message = validate_add_generative_widget_request(
        widget_type="chart",
        data=[{"quarter": "Q1", "value": 1}],
        chart_params={"chartType": "bar", "xKey": "quarter", "yKey": ["value"]},
    )

    assert message is None


# ---------------------------------------------------------------------------
# Round 1 typed-input migration: wire-shape and schema regressions.
# These tests pin the byte-shape of bridge commands produced by the migrated
# tools (manage_backends.endpoint_headers, manage_navigation_bar.tabs &
# rename_map, assign_tasks_to_agents.task_requests, add_generative_widget.
# chart_params) so accidental snake_case/camelCase shifts fail loudly. The
# expected shapes are sourced from the frontend handlers in
# terminalpro/src/components/AI/hooks/.
# ---------------------------------------------------------------------------


def _build_recording_server() -> tuple["RecordingBridgeState", object]:
    state = RecordingBridgeState()
    server = create_mcp_server(cast(BridgeSessionManager, state))
    return state, server


@pytest.mark.asyncio
async def test_manage_backends_typed_endpoint_headers_produce_snake_case_payload() -> None:
    """endpoint_headers should reach the bridge as snake_case BackendEndpointHeader objects."""
    state, server = _build_recording_server()

    await server.call_tool(
        "manage_backends",
        {
            "operation": "add",
            "name": "Demo",
            "url": "http://localhost:9000",
            "endpoint_headers": [
                {"key": "X-Auth", "value": "abc"},
                {"key": "token", "value": "xyz", "location": "query"},
            ],
        },
    )

    assert len(state.commands) == 1
    payload = state.commands[0].model_dump(mode="json")
    assert payload["endpoint_headers"] == [
        {"key": "X-Auth", "value": "abc", "location": "headers"},
        {"key": "token", "value": "xyz", "location": "query"},
    ]


@pytest.mark.asyncio
async def test_manage_navigation_bar_typed_tabs_produce_name_only_payload() -> None:
    """tabs should reach the bridge as [{name: str}] — no tab_id / tab_name keys."""
    state, server = _build_recording_server()

    await server.call_tool(
        "manage_navigation_bar",
        {
            "operation": "add_tabs",
            "tabs": [{"name": "AAPL Analysis"}, {"name": "Charts"}],
        },
    )

    assert len(state.commands) == 1
    payload = state.commands[0].model_dump(mode="json")
    assert payload["tabs"] == [{"name": "AAPL Analysis"}, {"name": "Charts"}]


@pytest.mark.asyncio
async def test_manage_navigation_bar_rejects_extra_tab_keys_via_pydantic() -> None:
    """tab_id and tab_name on tab inputs should fail at the Pydantic boundary.

    FastMCP propagates pydantic ``ValidationError`` directly from
    ``call_tool``; in production the transport layer maps that to an MCP-level
    error response. This test pins that the rejection happens at all.
    """
    from pydantic import ValidationError

    _, server = _build_recording_server()

    with pytest.raises(ValidationError) as excinfo:
        await server.call_tool(
            "manage_navigation_bar",
            {
                "operation": "add_tabs",
                "tabs": [{"tab_id": "aapl-analysis", "name": "AAPL Analysis"}],
            },
        )

    assert "tab_id" in str(excinfo.value)


@pytest.mark.asyncio
async def test_manage_navigation_bar_typed_rename_map_payload() -> None:
    """rename_map should reach the bridge as a {old: new} string-string dict."""
    state, server = _build_recording_server()

    await server.call_tool(
        "manage_navigation_bar",
        {
            "operation": "rename_tabs",
            "rename_map": {"old-tab": "New Tab"},
        },
    )

    assert len(state.commands) == 1
    payload = state.commands[0].model_dump(mode="json")
    assert payload["rename_map"] == {"old-tab": "New Tab"}


@pytest.mark.asyncio
async def test_assign_tasks_to_agents_typed_task_requests_use_snake_case() -> None:
    """task_requests fields should reach the bridge in snake_case (matches Zod schema)."""
    state, server = _build_recording_server()

    await server.call_tool(
        "assign_tasks_to_agents",
        {
            "task_requests": [
                {
                    "id": "task-1",
                    "description": "Review the dashboard",
                    "assigned_holder_url": "https://agents.example.com",
                    "assigned_agent_id": "agent-1",
                }
            ],
        },
    )

    assert len(state.commands) == 1
    payload = state.commands[0].model_dump(mode="json")
    assert payload["task_requests"] == [
        {
            "id": "task-1",
            "description": "Review the dashboard",
            "assigned_holder_url": "https://agents.example.com",
            "assigned_agent_id": "agent-1",
        }
    ]


@pytest.mark.asyncio
async def test_add_generative_widget_chart_params_preserves_camelcase() -> None:
    """chart_params keys must stay camelCase end-to-end — frontend Zod rejects snake_case."""
    state, server = _build_recording_server()

    await server.call_tool(
        "add_generative_widget",
        {
            "widget_type": "chart",
            "name": "Quarterly",
            "data": [{"quarter": "Q1", "value": 1}],
            "chart_params": {
                "chartType": "bar",
                "xKey": "quarter",
                "yKey": ["value"],
            },
        },
    )

    assert len(state.commands) == 1
    payload = state.commands[0].model_dump(mode="json")
    assert payload["chart_params"] == {
        "chartType": "bar",
        "xKey": "quarter",
        "yKey": ["value"],
    }


@pytest.mark.asyncio
async def test_migrated_params_advertise_structured_schema_not_strings() -> None:
    """The 5 migrated params should advertise as array/object, and the old _json
    string params should be gone from every tool's input schema."""
    server = create_mcp_server(
        BridgeSessionManager(
            base_url="http://127.0.0.1:8787",
            websocket_path="/bridge/ws",
            command_timeout_seconds=1,
        )
    )

    tools = await server.list_tools()
    by_name = {t.name: t for t in tools}

    def schema_for(tool_name: str, prop: str) -> str:
        params = by_name[tool_name].parameters
        return json.dumps(params.get("properties", {}).get(prop, {}))

    def properties(tool_name: str) -> set[str]:
        params = by_name[tool_name].parameters
        return set((params.get("properties") or {}).keys())

    # Round 1 typed migrations: each param now advertises a structured type
    # somewhere in its schema. (Pydantic emits anyOf for `list[X] | None`.)
    assert '"array"' in schema_for("manage_backends", "endpoint_headers")
    assert '"array"' in schema_for("manage_navigation_bar", "tabs")
    assert '"object"' in schema_for("manage_navigation_bar", "rename_map")
    assert '"array"' in schema_for("assign_tasks_to_agents", "task_requests")
    assert '"object"' in schema_for("add_generative_widget", "chart_params")

    # Round 2 typed migrations: the dynamic dict params are now objects, and
    # add_generative_widget.data is a string-or-array union.
    assert '"object"' in schema_for("get_widget_data", "data_args")
    assert '"object"' in schema_for("get_widget_data", "ssm_request")
    assert '"object"' in schema_for("get_params_options", "data_args")
    assert '"object"' in schema_for("create_widget", "data_args")
    assert '"object"' in schema_for("create_widget", "ui_args")
    assert '"object"' in schema_for("update_widget", "data_args")
    assert '"object"' in schema_for("update_widget", "ui_args")
    add_generative_data_schema = schema_for("add_generative_widget", "data")
    assert '"string"' in add_generative_data_schema
    assert '"array"' in add_generative_data_schema

    # All Round 1 + Round 2 _json string params are gone from every tool surface.
    assert "endpoint_headers_json" not in properties("manage_backends")
    assert "tabs_json" not in properties("manage_navigation_bar")
    assert "rename_map_json" not in properties("manage_navigation_bar")
    assert "task_requests_json" not in properties("assign_tasks_to_agents")
    assert "chart_params_json" not in properties("add_generative_widget")
    assert "data_args_json" not in properties("get_widget_data")
    assert "ssm_request_json" not in properties("get_widget_data")
    assert "data_args_json" not in properties("get_params_options")
    assert "data_args_json" not in properties("create_widget")
    assert "ui_args_json" not in properties("create_widget")
    assert "data_args_json" not in properties("update_widget")
    assert "ui_args_json" not in properties("update_widget")
    assert "data_json" not in properties("add_generative_widget")


# ---------------------------------------------------------------------------
# Single-call coverage for each tool in the surface — pinned bridge command
# shape and the documented validation rejections. Chained-flow coverage lives
# in tests/smoke/PROMPTS.md (manual) until a smoke-scenario pytest mirror lands.
# ---------------------------------------------------------------------------

# ---------- get_workspace_snapshot ----------


@pytest.mark.asyncio
async def test_get_workspace_snapshot_emits_snapshot_command() -> None:
    """The snapshot tool should send a no-arg get_workspace_snapshot command."""
    state, server = _build_recording_server()

    await server.call_tool("get_workspace_snapshot", {})

    assert len(state.commands) == 1
    assert state.commands[0].command == "get_workspace_snapshot"


# ---------- manage_dashboard (create + update operations) ----------


@pytest.mark.asyncio
async def test_manage_dashboard_create_emits_create_command_with_default_activate() -> None:
    """Create operation should default activate=True and pass name through."""
    state, server = _build_recording_server()

    await server.call_tool(
        "manage_dashboard", {"operation": "create", "name": "Smoke"}
    )

    cmd = state.commands[0]
    assert isinstance(cmd, ManageDashboardCommand)
    assert cmd.operation == "create"
    assert cmd.name == "Smoke"
    assert cmd.activate is True


@pytest.mark.asyncio
async def test_manage_dashboard_create_rejects_missing_name() -> None:
    """Create requires name and should refuse to dispatch without it."""
    state, server = _build_recording_server()

    result = await server.call_tool("manage_dashboard", {"operation": "create"})

    assert state.commands == []
    assert result.structured_content["ok"] is False


@pytest.mark.asyncio
async def test_manage_dashboard_update_requires_dashboard_id_and_name() -> None:
    """Update requires both dashboard_id and name."""
    state, server = _build_recording_server()

    result = await server.call_tool(
        "manage_dashboard", {"operation": "update", "name": "X"}
    )

    assert state.commands == []
    assert result.structured_content["ok"] is False


# ---------- navigate_workspace (dashboard operation) ----------


@pytest.mark.asyncio
async def test_navigate_workspace_dashboard_operation_emits_command() -> None:
    """The dashboard operation should emit a navigate_workspace command."""
    state, server = _build_recording_server()

    await server.call_tool(
        "navigate_workspace",
        {"operation": "dashboard", "dashboard_id": "d-1", "tab_id": "t-1"},
    )

    cmd = state.commands[0]
    assert isinstance(cmd, NavigateWorkspaceCommand)
    assert cmd.operation == "dashboard"
    assert cmd.dashboard_id == "d-1"
    assert cmd.tab_id == "t-1"


@pytest.mark.asyncio
async def test_navigate_workspace_dashboard_requires_dashboard_id() -> None:
    """The dashboard operation must reject missing dashboard_id."""
    state, server = _build_recording_server()

    result = await server.call_tool("navigate_workspace", {"operation": "dashboard"})

    assert state.commands == []
    assert result.structured_content["ok"] is False


# ---------- list_available_widgets ----------


@pytest.mark.asyncio
async def test_list_available_widgets_with_filters_passes_through() -> None:
    """origin and backend_id filters should reach the bridge command."""
    state, server = _build_recording_server()

    await server.call_tool(
        "list_available_widgets",
        {"origin": "OpenBB Polymarket", "backend_id": "b-1"},
    )

    cmd = state.commands[0]
    assert cmd.command == "list_available_widgets"
    assert cmd.origin == "OpenBB Polymarket"
    assert cmd.backend_id == "b-1"


@pytest.mark.asyncio
async def test_list_available_widgets_with_no_filters_emits_unfiltered_request() -> None:
    """Calling without filters should still emit the command with both filters None."""
    state, server = _build_recording_server()

    await server.call_tool("list_available_widgets", {})

    cmd = state.commands[0]
    assert cmd.origin is None
    assert cmd.backend_id is None


# ---------- get_widget_schema ----------


@pytest.mark.asyncio
async def test_get_widget_schema_happy_path_emits_command() -> None:
    """Happy path passes origin and widget_id through unchanged."""
    state, server = _build_recording_server()

    await server.call_tool(
        "get_widget_schema",
        {"origin": "OpenBB Polymarket", "widget_id": "event_markets"},
    )

    cmd = state.commands[0]
    assert isinstance(cmd, GetWidgetSchemaCommand)
    assert cmd.origin == "OpenBB Polymarket"
    assert cmd.widget_id == "event_markets"


@pytest.mark.asyncio
async def test_get_widget_schema_rejects_missing_origin() -> None:
    """Tool should refuse to dispatch without origin even though the model allows it."""
    state, server = _build_recording_server()

    result = await server.call_tool(
        "get_widget_schema", {"widget_id": "event_markets"}
    )

    assert state.commands == []
    assert result.structured_content["ok"] is False


# ---------- get_params_options ----------


@pytest.mark.asyncio
async def test_get_params_options_emits_query_payload() -> None:
    """The tool should translate the inputs into a one-item query payload."""
    state, server = _build_recording_server()

    await server.call_tool(
        "get_params_options",
        {
            "origin": "OpenBB Polymarket",
            "widget_id": "search_events",
            "param_name": "tag",
            "data_args": {"search": "iran"},
        },
    )

    cmd = state.commands[0]
    assert cmd.command == "get_params_options"
    assert cmd.param_options_queries == [
        {
            "origin": "OpenBB Polymarket",
            "id": "search_events",
            "param": "tag",
            "options_endpoint_input_args": {"search": "iran"},
        }
    ]


# ---------- create_widget ----------


@pytest.mark.asyncio
async def test_create_widget_happy_path_carries_data_args_into_command() -> None:
    """data_args_json should be parsed and carried into the widget config."""
    state, server = _build_recording_server()

    await server.call_tool(
        "create_widget",
        {
            "origin": "OpenBB Polymarket",
            "widget_id": "event_markets",
            "data_args": {"event_id": "158299"},
        },
    )

    cmd = state.commands[0]
    assert isinstance(cmd, CreateWidgetCommand)
    assert cmd.backend_name == "OpenBB Polymarket"
    assert cmd.widget_id == "event_markets"
    assert cmd.config is not None
    assert cmd.config.data_args == {"event_id": "158299"}


@pytest.mark.asyncio
async def test_create_widget_rejects_rich_note_via_tool_error() -> None:
    """create_widget must refuse rich_note and route the caller to add_generative_widget."""
    state, server = _build_recording_server()

    result = await server.call_tool(
        "create_widget", {"origin": "OpenBB Workspace", "widget_id": "rich_note"}
    )

    assert state.commands == []
    assert result.structured_content["ok"] is False
    assert "rich_note" in result.structured_content["message"]
    assert "add_generative_widget" in result.structured_content["message"]


@pytest.mark.asyncio
async def test_create_widget_requires_origin_and_widget_id() -> None:
    """Missing origin or widget_id should fail before any bridge dispatch."""
    state, server = _build_recording_server()

    result = await server.call_tool("create_widget", {})

    assert state.commands == []
    assert result.structured_content["ok"] is False


# ---------- read_widget ----------


@pytest.mark.asyncio
async def test_read_widget_emits_command_with_widget_uuid() -> None:
    """read_widget should pass widget_uuid through unchanged."""
    state, server = _build_recording_server()

    await server.call_tool("read_widget", {"widget_uuid": "w-1"})

    cmd = state.commands[0]
    assert cmd.command == "read_widget"
    assert cmd.widget_uuid == "w-1"


# ---------- update_widget ----------


@pytest.mark.asyncio
async def test_update_widget_happy_path_carries_config() -> None:
    """update_widget should carry data_args into the widget config."""
    state, server = _build_recording_server()

    await server.call_tool(
        "update_widget",
        {"widget_uuid": "w-1", "data_args": {"limit": 5}},
    )

    cmd = state.commands[0]
    assert isinstance(cmd, UpdateWidgetCommand)
    assert cmd.widget_uuid == "w-1"
    assert cmd.config.data_args == {"limit": 5}


@pytest.mark.asyncio
async def test_update_widget_rejects_layout_ui_args_with_routing_hint() -> None:
    """update_widget must refuse layout-flavored ui_args and point at update_widget_layout."""
    state, server = _build_recording_server()

    result = await server.call_tool(
        "update_widget",
        {
            "widget_uuid": "w-1",
            "ui_args": {"x": 0, "y": 2, "w": 40, "h": 12},
        },
    )

    assert state.commands == []
    assert result.structured_content["ok"] is False
    assert "update_widget_layout" in result.structured_content["message"]


# ---------- update_widget_layout ----------


@pytest.mark.asyncio
async def test_update_widget_layout_emits_update_dashboard_layout_bridge_command() -> None:
    """The MCP tool is named update_widget_layout but emits the legacy
    update_dashboard_layout command name on the bridge. This test pins that
    asymmetry so a future rename is loud, not silent."""
    state, server = _build_recording_server()

    await server.call_tool(
        "update_widget_layout",
        {"x": 0.0, "y": 2.0, "w": 40.0, "h": 12.0, "widget_uuid": "w-1"},
    )

    cmd = state.commands[0]
    assert isinstance(cmd, UpdateDashboardLayoutCommand)
    assert cmd.command == "update_dashboard_layout"
    assert (cmd.x, cmd.y, cmd.w, cmd.h) == (0.0, 2.0, 40.0, 12.0)
    assert cmd.widget_uuid == "w-1"


# ---------- delete_widget ----------


@pytest.mark.asyncio
async def test_delete_widget_emits_command_with_uuid() -> None:
    """delete_widget should pass widget_uuid through unchanged."""
    state, server = _build_recording_server()

    await server.call_tool("delete_widget", {"widget_uuid": "w-1"})

    cmd = state.commands[0]
    assert cmd.command == "delete_widget"
    assert cmd.widget_uuid == "w-1"


# ---------- get_widget_data ----------


@pytest.mark.asyncio
async def test_get_widget_data_emits_data_sources_payload() -> None:
    """get_widget_data should translate inputs into a one-item data_sources list."""
    state, server = _build_recording_server()

    await server.call_tool(
        "get_widget_data",
        {
            "origin": "OpenBB Polymarket",
            "widget_id": "event_markets",
            "data_args": {"event_id": "158299"},
            "widget_uuid": "w-1",
        },
    )

    cmd = state.commands[0]
    assert cmd.command == "get_widget_data"
    assert cmd.data_sources == [
        {
            "origin": "OpenBB Polymarket",
            "id": "event_markets",
            "input_args": {"event_id": "158299"},
            "widget_uuid": "w-1",
            "ssm_request": None,
        }
    ]


# ---------- manage_apps ----------


@pytest.mark.asyncio
async def test_manage_apps_list_emits_command() -> None:
    """manage_apps list should emit a list operation with backend_id."""
    state, server = _build_recording_server()

    await server.call_tool("manage_apps", {"operation": "list", "backend_id": "b-1"})

    cmd = state.commands[0]
    assert cmd.command == "manage_apps"
    assert cmd.operation == "list"
    assert cmd.backend_id == "b-1"


@pytest.mark.asyncio
async def test_manage_apps_instantiate_with_app_name() -> None:
    """instantiate should carry app_name through to the bridge command."""
    state, server = _build_recording_server()

    await server.call_tool(
        "manage_apps",
        {
            "operation": "instantiate",
            "backend_id": "b-1",
            "app_name": "Daily Briefing",
        },
    )

    cmd = state.commands[0]
    assert cmd.operation == "instantiate"
    assert cmd.app_name == "Daily Briefing"


@pytest.mark.asyncio
async def test_manage_apps_read_requires_app_name_or_template_id() -> None:
    """read needs at least one of app_name or template_id."""
    state, server = _build_recording_server()

    result = await server.call_tool(
        "manage_apps", {"operation": "read", "backend_id": "b-1"}
    )

    assert state.commands == []
    assert result.structured_content["ok"] is False


@pytest.mark.asyncio
async def test_manage_apps_requires_backend_id() -> None:
    """backend_id is a required parameter; pydantic rejects calls without it."""
    from pydantic import ValidationError

    state, server = _build_recording_server()

    with pytest.raises(ValidationError):
        await server.call_tool("manage_apps", {"operation": "list"})

    assert state.commands == []


# ---------- manage_backends (operation matrix beyond endpoint_headers) ----------


@pytest.mark.asyncio
async def test_manage_backends_list_emits_command() -> None:
    """list operation should not require a backend_id."""
    state, server = _build_recording_server()

    await server.call_tool("manage_backends", {"operation": "list"})

    cmd = state.commands[0]
    assert cmd.command == "manage_backends"
    assert cmd.operation == "list"


@pytest.mark.asyncio
async def test_manage_backends_add_requires_name_and_url() -> None:
    """add must reject calls missing either name or url."""
    state, server = _build_recording_server()

    result = await server.call_tool(
        "manage_backends", {"operation": "add", "name": "Demo"}
    )

    assert state.commands == []
    assert result.structured_content["ok"] is False


@pytest.mark.asyncio
async def test_manage_backends_remove_requires_backend_id() -> None:
    """remove must reject calls without backend_id."""
    state, server = _build_recording_server()

    result = await server.call_tool("manage_backends", {"operation": "remove"})

    assert state.commands == []
    assert result.structured_content["ok"] is False


@pytest.mark.asyncio
async def test_manage_backends_update_requires_at_least_one_field() -> None:
    """update with just backend_id but no fields to change should reject."""
    state, server = _build_recording_server()

    result = await server.call_tool(
        "manage_backends", {"operation": "update", "backend_id": "b-1"}
    )

    assert state.commands == []
    assert result.structured_content["ok"] is False


# ---------- manage_navigation_bar (rename_tabs validation) ----------


@pytest.mark.asyncio
async def test_manage_navigation_bar_rename_tabs_requires_rename_map() -> None:
    """rename_tabs without a rename_map should refuse to dispatch."""
    state, server = _build_recording_server()

    result = await server.call_tool(
        "manage_navigation_bar", {"operation": "rename_tabs"}
    )

    assert state.commands == []
    assert result.structured_content["ok"] is False


# ---------- get_skill_content ----------


@pytest.mark.asyncio
async def test_get_skill_content_emits_command_with_slug_and_reason() -> None:
    """get_skill_content should pass slug and optional reason through unchanged."""
    state, server = _build_recording_server()

    await server.call_tool(
        "get_skill_content", {"slug": "my-skill", "reason": "smoke test"}
    )

    cmd = state.commands[0]
    assert cmd.command == "get_skill_content"
    assert cmd.slug == "my-skill"
    assert cmd.reason == "smoke test"
