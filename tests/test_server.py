"""Server metadata tests for the Workspace MCP tool surface."""

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
    validate_navigation_tabs,
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

    assert {prompt.name for prompt in prompts} == {"workspace_tool_usage"}
    assert prompts[0].description == (
        "Generic guidance for using the OpenBB Workspace MCP tool surface."
    )
    assert "get_workspace_snapshot" in SERVER_INSTRUCTIONS
    assert "Pass origin, widget_id, and data_args_json" in SERVER_INSTRUCTIONS
    assert "Do not use create_widget for rich_note" in SERVER_INSTRUCTIONS
    assert "The grid is 40 columns wide" in SERVER_INSTRUCTIONS
    assert "grid_data defaults and min/max layout constraints" in SERVER_INSTRUCTIONS
    assert "deterministic plain-create subset" in SERVER_INSTRUCTIONS
    assert "requires_options_lookup=true" in SERVER_INSTRUCTIONS
    assert "exact paramName from the schema as param_name" in SERVER_INSTRUCTIONS
    assert "options_lookup_params" in SERVER_INSTRUCTIONS
    assert "dashboard_id, dashboard_composition, and skills" in SERVER_INSTRUCTIONS
    assert "data_args_json" in SERVER_INSTRUCTIONS
    assert "data_args_json must be a JSON object string" in SERVER_INSTRUCTIONS
    assert "data_json as the raw text" in SERVER_INSTRUCTIONS
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
async def test_text_generative_widgets_accept_raw_data_json_strings() -> None:
    """Notes and HTML widgets should accept plain string content."""
    state = RecordingBridgeState()
    server = create_mcp_server(cast(BridgeSessionManager, state))

    result = await server.call_tool(
        "add_generative_widget",
        {
            "widget_type": "note",
            "name": "Briefing",
            "data_json": "# Briefing\n\nRaw markdown body.",
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


def test_validate_navigation_tabs_rejects_tab_id_tab_name_shape() -> None:
    """Navigation-bar tabs must use the browser helper's {name} shape."""
    response = validate_navigation_tabs(
        "add_tabs",
        [{"tab_id": "aapl-analysis", "tab_name": "AAPL Analysis"}],
    )

    assert response is not None
    assert response["ok"] is False
    assert response["command"] == "manage_navigation_bar"
    assert response["message"] == (
        "manage_navigation_bar tabs_json items must not include tab_id or tab_name; "
        'use only {"name":"AAPL Analysis"}. The tab_id is generated as the slug of name.'
    )


def test_validate_navigation_tabs_rejects_extra_tab_id_with_name() -> None:
    """Navigation-bar tabs should not accept ignored tab_id fields."""
    response = validate_navigation_tabs(
        "add_tabs",
        [{"tab_id": "aapl-analysis", "name": "AAPL Analysis"}],
    )

    assert response is not None
    assert response["ok"] is False
    assert response["message"] == (
        "manage_navigation_bar tabs_json items must not include tab_id or tab_name; "
        'use only {"name":"AAPL Analysis"}. The tab_id is generated as the slug of name.'
    )


def test_validate_navigation_tabs_accepts_name_shape() -> None:
    """Navigation-bar tabs should accept the documented {name} shape."""
    assert validate_navigation_tabs("add_tabs", [{"name": "AAPL Analysis"}]) is None


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
