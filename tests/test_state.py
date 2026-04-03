"""Unit tests for the sidecar state manager."""

import asyncio
from uuid import UUID

import pytest
from openbb_ai.models import AgentTool

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
                    "widgets": {"primary": [], "secondary": [], "extra": []},
                    "context": [],
                    "artifacts": [],
                    "files": [],
                    "tools": [
                        AgentTool(
                            server_id="local-docs",
                            name="search_docs",
                            url="http://127.0.0.1:5050/mcp",
                        ).model_dump(mode="json")
                    ],
                    "skills": [],
                },
            ).model_dump(mode="json"),
        }
    )

    result = await task

    assert result.ok is True
    assert result.command == "get_workspace_snapshot"
    assert isinstance(result.data, dict)
    assert result.data["workspace_state"]["current_page_context"] == "dashboard"
    assert result.data["tools"][0]["name"] == "search_docs"


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
    assert result.data == {"widget_uuid": "widget-1"}


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
