"""Unit tests for the sidecar state manager."""

import asyncio
from uuid import UUID

import pytest

from workspace_mcp.models import (
    BrowserSessionStartRequest,
    WorkspaceCommandResult,
)
from workspace_mcp.state import BrowserUnavailableError, BridgeSessionManager


class FakeSocket:
    """Capture JSON messages sent to the browser."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, data: object) -> None:
        assert isinstance(data, dict)
        self.messages.append(data)


@pytest.fixture
def bridge_manager() -> BridgeSessionManager:
    """Create a bridge manager with a short command timeout."""
    return BridgeSessionManager(
        base_url="http://127.0.0.1:8787",
        websocket_path="/bridge/ws",
        command_timeout_seconds=0.25,
    )


@pytest.mark.asyncio
async def test_snapshot_requires_connected_browser(
    bridge_manager: BridgeSessionManager,
) -> None:
    """Snapshot commands should fail cleanly when no browser is connected."""
    with pytest.raises(BrowserUnavailableError):
        await bridge_manager.execute_command({"command": "get_workspace_snapshot"})


@pytest.mark.asyncio
async def test_get_workspace_snapshot_round_trip(
    bridge_manager: BridgeSessionManager,
) -> None:
    """Snapshot requests should be forwarded to the browser on demand."""
    socket = await connect_browser(bridge_manager)

    task = asyncio.create_task(
        bridge_manager.execute_command({"command": "get_workspace_snapshot"})
    )

    await asyncio.sleep(0)
    assert socket.messages[0]["type"] == "command_request"
    request_id = socket.messages[0]["command"]["request_id"]

    await bridge_manager.handle_browser_message(
        {
            "type": "command_result",
            "result": WorkspaceCommandResult(
                ok=True,
                command="get_workspace_snapshot",
                request_id=request_id,
                message="Workspace snapshot retrieved.",
                data={
                    "generated_at": 1,
                    "workspace_state": {
                        "current_page_context": "dashboard",
                        "current_dashboard_uuid": str(
                            UUID("00000000-0000-0000-0000-000000000001")
                        ),
                    },
                    "workspace_options": ["mcp-tools"],
                    "dashboards": [
                        {
                            "dashboard_id": "dashboard-1",
                            "name": "Macro",
                            "is_active": True,
                            "widget_count": 1,
                            "tab_count": 1,
                        }
                    ],
                    "dashboard_composition": {
                        "id": "dashboard-1",
                        "name": "Macro",
                        "current_tab_id": "__no_tab__",
                        "current_tab_name": "__no_tab__",
                        "tabs": [
                            {
                                "tab_id": "__no_tab__",
                                "tab_name": "__no_tab__",
                                "widgets": [
                                    {
                                        "widget_uuid": "widget-1",
                                        "name": "Market Snapshot",
                                    }
                                ],
                                "layout": [
                                    {
                                        "widget_uuid": "widget-1",
                                        "x": 0,
                                        "y": 0,
                                        "w": 40,
                                        "h": 12,
                                    }
                                ],
                            }
                        ],
                        "groups": [],
                    },
                    "skills": [
                        {
                            "slug": "macro-research",
                            "name": "Macro Research",
                        }
                    ],
                },
            ).model_dump(mode="json"),
        }
    )

    result = await task

    assert result.ok is True
    assert result.command == "get_workspace_snapshot"
    assert isinstance(result.data, dict)
    assert result.data["workspace_state"]["current_page_context"] == "dashboard"
    assert result.data["dashboards"][0]["dashboard_id"] == "dashboard-1"
    assert result.data["dashboard_composition"]["tabs"][0]["layout"][0]["w"] == 40
    assert result.data["skills"][0]["slug"] == "macro-research"
    assert "tools" not in result.data


@pytest.mark.asyncio
async def test_execute_command_round_trip(
    bridge_manager: BridgeSessionManager,
) -> None:
    """Mutating commands should be forwarded to the browser and resolve on reply."""
    socket = await connect_browser(bridge_manager)

    task = asyncio.create_task(
        bridge_manager.execute_command(
            {
                "command": "delete_widget",
                "dashboard_id": "dashboard-1",
                "widget_uuid": "widget-1",
            }
        )
    )

    await asyncio.sleep(0)
    assert socket.messages[0]["type"] == "command_request"
    request_id = socket.messages[0]["command"]["request_id"]

    await bridge_manager.handle_browser_message(
        {
            "type": "command_result",
            "result": WorkspaceCommandResult(
                ok=True,
                command="delete_widget",
                request_id=request_id,
                message="Deleted.",
                data={"widget_uuid": "widget-1"},
            ).model_dump(mode="json"),
        }
    )

    result = await task
    assert result.ok is True
    assert result.data["widget_uuid"] == "widget-1"
    assert "session_context" in result.data


@pytest.mark.asyncio
async def test_invalid_browser_payload_fails_pending_command_without_disconnect(
    bridge_manager: BridgeSessionManager,
) -> None:
    """Malformed browser frames should fail commands without tearing down the session."""
    socket = await connect_browser(bridge_manager)

    task = asyncio.create_task(
        bridge_manager.execute_command({"command": "list_available_widgets"})
    )

    await asyncio.sleep(0)
    request_id = socket.messages[0]["command"]["request_id"]

    await bridge_manager.handle_browser_message({"type": "command_result"})

    result = await task
    assert result.ok is False
    assert result.command == "list_available_widgets"
    assert result.request_id == request_id
    assert result.error is not None
    assert result.error.code == "invalid_request"
    assert "invalid websocket payload" in result.message

    follow_up_task = asyncio.create_task(
        bridge_manager.execute_command({"command": "get_workspace_snapshot"})
    )

    await asyncio.sleep(0)
    follow_up_request_id = socket.messages[1]["command"]["request_id"]
    await bridge_manager.handle_browser_message(
        {
            "type": "command_result",
            "result": WorkspaceCommandResult(
                ok=True,
                command="get_workspace_snapshot",
                request_id=follow_up_request_id,
                message="Workspace snapshot retrieved.",
                data={
                    "generated_at": 1,
                    "workspace_state": None,
                },
            ).model_dump(mode="json"),
        }
    )

    follow_up_result = await follow_up_task
    assert follow_up_result.ok is True


@pytest.mark.asyncio
async def test_read_widget_accepts_widget_id_alias(
    bridge_manager: BridgeSessionManager,
) -> None:
    """Widget-instance commands should preserve widget_id aliases for the browser."""
    socket = await connect_browser(bridge_manager)

    task = asyncio.create_task(
        bridge_manager.execute_command(
            {
                "command": "read_widget",
                "dashboard_id": "dashboard-1",
                "widget_id": "price_history",
            }
        )
    )

    await asyncio.sleep(0)
    command = socket.messages[0]["command"]
    request_id = command["request_id"]

    assert command["widget_id"] == "price_history"
    assert command["widget_uuid"] is None

    await bridge_manager.handle_browser_message(
        {
            "type": "command_result",
            "result": WorkspaceCommandResult(
                ok=True,
                command="read_widget",
                request_id=request_id,
                message="Widget loaded.",
                data={"widget_uuid": "widget-instance-1"},
            ).model_dump(mode="json"),
        }
    )

    result = await task
    assert result.ok is True
    assert result.data["widget_uuid"] == "widget-instance-1"
    assert "session_context" in result.data


@pytest.mark.asyncio
async def test_stale_disconnect_does_not_drop_replacement_browser(
    bridge_manager: BridgeSessionManager,
) -> None:
    """Closing an old websocket should not mark the replacement browser offline."""
    first_session = await bridge_manager.start_session(BrowserSessionStartRequest())
    first_socket = FakeSocket()
    await bridge_manager.connect_browser(
        session_id=first_session.session.session_id,
        token=first_session.session.token,
        socket=first_socket,
    )

    replacement_session = await bridge_manager.start_session(BrowserSessionStartRequest())
    replacement_socket = FakeSocket()
    await bridge_manager.connect_browser(
        session_id=replacement_session.session.session_id,
        token=replacement_session.session.token,
        socket=replacement_socket,
    )

    await bridge_manager.disconnect_browser(session_id=first_session.session.session_id)

    task = asyncio.create_task(
        bridge_manager.execute_command({"command": "get_workspace_snapshot"})
    )
    await asyncio.sleep(0)

    request_id = replacement_socket.messages[0]["command"]["request_id"]
    await bridge_manager.handle_browser_message(
        {
            "type": "command_result",
            "result": WorkspaceCommandResult(
                ok=True,
                command="get_workspace_snapshot",
                request_id=request_id,
                message="Workspace snapshot retrieved.",
                data={
                    "generated_at": 1,
                    "workspace_state": None,
                },
            ).model_dump(mode="json"),
        }
    )

    result = await task

    assert result.ok is True


@pytest.mark.asyncio
async def test_session_context_is_injected_into_successful_results(
    bridge_manager: BridgeSessionManager,
) -> None:
    """Successful command results should carry the tracked session context."""
    socket = await connect_browser(bridge_manager)

    await bridge_manager.handle_browser_message(
        {
            "type": "session_context_changed",
            "session": {
                "current_dashboard_id": "dash-active",
                "current_tab_id": "tab-overview",
            },
        }
    )

    task = asyncio.create_task(
        bridge_manager.execute_command(
            {"command": "read_widget", "widget_uuid": "widget-1"}
        )
    )

    await asyncio.sleep(0)
    request_id = socket.messages[0]["command"]["request_id"]

    await bridge_manager.handle_browser_message(
        {
            "type": "command_result",
            "result": WorkspaceCommandResult(
                ok=True,
                command="read_widget",
                request_id=request_id,
                message="Widget loaded.",
                data={"widget_uuid": "widget-1"},
            ).model_dump(mode="json"),
        }
    )

    result = await task
    assert result.data["session_context"] == {
        "current_dashboard_uuid": "dash-active",
        "current_tab_id": "tab-overview",
    }


@pytest.mark.asyncio
async def test_session_context_is_not_injected_into_error_results(
    bridge_manager: BridgeSessionManager,
) -> None:
    """Error results have no data dict to enrich; injection must be skipped."""
    socket = await connect_browser(bridge_manager)

    await bridge_manager.handle_browser_message(
        {
            "type": "session_context_changed",
            "session": {
                "current_dashboard_id": "dash-active",
                "current_tab_id": None,
            },
        }
    )

    task = asyncio.create_task(
        bridge_manager.execute_command(
            {"command": "read_widget", "widget_uuid": "missing"}
        )
    )

    await asyncio.sleep(0)
    request_id = socket.messages[0]["command"]["request_id"]

    await bridge_manager.handle_browser_message(
        {
            "type": "command_result",
            "result": WorkspaceCommandResult(
                ok=False,
                command="read_widget",
                request_id=request_id,
                message="Widget not found.",
            ).model_dump(mode="json"),
        }
    )

    result = await task
    assert result.ok is False
    assert result.data is None


async def connect_browser(bridge_manager: BridgeSessionManager) -> FakeSocket:
    """Start a bridge session and attach a fake browser socket."""
    session = await bridge_manager.start_session(BrowserSessionStartRequest())
    socket = FakeSocket()
    await bridge_manager.connect_browser(
        session_id=session.session.session_id,
        token=session.session.token,
        socket=socket,
    )
    return socket
