"""Server metadata tests for the Workspace MCP tool surface."""

import pytest

from workspace_mcp.models import (
    AddGenerativeWidgetCommand,
    CreateWidgetCommand,
    ManageNavigationBarCommand,
    ParamOptionsRequest,
    UpdateWidgetCommand,
    WidgetDataRequest,
    WorkspaceWidgetConfig,
)
from workspace_mcp.server import (
    SERVER_INSTRUCTIONS,
    create_mcp_server,
    data_source_payloads,
    invalid_request,
    param_options_payloads,
    validate_add_generative_widget_request,
)
from workspace_mcp.state import BridgeSessionManager


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
    assert "{origin, widget_id, data_args" in SERVER_INSTRUCTIONS


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
