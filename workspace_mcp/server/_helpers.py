"""Shared utilities for Workspace MCP tool handlers.

Response builders, command-payload translators, and small predicates used by
more than one tool module.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from workspace_mcp.models import ParamOptionsRequest, WidgetDataRequest
from workspace_mcp.state import BridgeSessionManager


type ToolResponse = dict[str, Any]
type CommandRunner = Callable[[Any], Awaitable[ToolResponse]]
type NavigationOperationName = str
type GenerativeWidgetTypeName = str


# ---------------------------------------------------------------------------
# Widget config builders
# ---------------------------------------------------------------------------


def widget_config(
    *,
    data_args: dict[str, Any] | None,
    ui_args: dict[str, Any] | None,
):
    """Build widget config only when the caller supplied config values."""
    from workspace_mcp.models import WorkspaceWidgetConfig

    if data_args is None and ui_args is None:
        return None
    return WorkspaceWidgetConfig(data_args=data_args, ui_args=ui_args)


def required_widget_config(
    *, data_args: dict[str, Any] | None, ui_args: dict[str, Any] | None
):
    """Build widget config for commands that always expect the field."""
    from workspace_mcp.models import WorkspaceWidgetConfig

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


# ---------------------------------------------------------------------------
# Tool error envelopes
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Browser-bridge payload translators
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Prompt content builders
# ---------------------------------------------------------------------------


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
