"""Typed protocol models shared by the sidecar HTTP, websocket, and MCP layers."""

from typing import Annotated, Any, Literal
from uuid import uuid4

from openbb_ai.models import AgentTool, WorkspaceState
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

type BridgeErrorCode = Literal[
    "invalid_request",
    "unauthorized",
    "unavailable",
    "timeout",
    "command_failed",
    "unknown",
]
type NavigationOperation = Literal["create", "add_tabs", "remove_tabs", "rename_tabs"]
type GenerativeWidgetType = Literal["note", "table", "chart", "html"]


def new_request_id() -> str:
    """Create a stable request identifier for browser command roundtrips."""
    return f"cmd_{uuid4().hex}"


def widget_groups() -> dict[str, list[dict[str, Any]]]:
    """Return the default widget buckets for a workspace snapshot."""
    return {"primary": [], "secondary": [], "extra": []}


class Model(BaseModel):
    """Base model with strict validation and snake_case serialization."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class BridgeError(Model):
    """Structured error returned by the sidecar."""

    code: BridgeErrorCode
    message: str
    details: dict[str, Any] | None = None
    retryable: bool = False


class BrowserSessionStartRequest(Model):
    """Start a browser bridge session."""

    client_name: str = "workspace-ui"
    current_dashboard_id: str | None = None


class BrowserSession(Model):
    """Active browser session metadata."""

    session_id: str
    token: str
    client_name: str
    current_dashboard_id: str | None = None


class BrowserSessionStartResponse(Model):
    """Session bootstrap payload returned to the browser."""

    session: BrowserSession
    websocket_url: str


class WorkspaceSnapshot(Model):
    """Bridge snapshot envelope around canonical OpenBB workspace models.

    The sidecar keeps the transport envelope local, but it reuses
    ``openbb_ai.models.WorkspaceState`` and ``openbb_ai.models.AgentTool`` so
    there is one source of truth for the main workspace payloads.
    """

    generated_at: int
    workspace_state: WorkspaceState | None = None
    workspace_options: list[str] = Field(default_factory=list)
    widgets: dict[str, list[dict[str, Any]]] = Field(default_factory=widget_groups)
    context: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    files: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[AgentTool] = Field(default_factory=list)
    skills: list[dict[str, Any]] = Field(default_factory=list)


class WorkspaceWidgetConfig(Model):
    """Widget configuration passed through to the Workspace frontend."""

    data_args: dict[str, Any] | None = None
    ui_args: dict[str, Any] | None = None


class ReadWidgetCommand(Model):
    """Read one widget from the active dashboard."""

    command: Literal["read_widget"]
    request_id: str | None = None
    dashboard_id: str | None = None
    widget_uuid: str


class CreateWidgetCommand(Model):
    """Create one widget on the active dashboard."""

    command: Literal["create_widget"]
    request_id: str | None = None
    dashboard_id: str
    backend_name: str
    widget_id: str
    config: WorkspaceWidgetConfig | None = None


class UpdateWidgetCommand(Model):
    """Update one widget on the active dashboard."""

    command: Literal["update_widget"]
    request_id: str | None = None
    dashboard_id: str
    widget_uuid: str
    config: WorkspaceWidgetConfig


class DeleteWidgetCommand(Model):
    """Delete one widget from the active dashboard."""

    command: Literal["delete_widget"]
    request_id: str | None = None
    dashboard_id: str
    widget_uuid: str


class ManageNavigationBarCommand(Model):
    """Create or mutate navigation tabs."""

    command: Literal["manage_navigation_bar"]
    request_id: str | None = None
    dashboard_id: str
    operation: NavigationOperation
    tabs: list[dict[str, Any]] = Field(default_factory=list)
    rename_map: dict[str, str] = Field(default_factory=dict)


class AddGenerativeWidgetCommand(Model):
    """Create a generated widget from inline data."""

    command: Literal["add_generative_widget"]
    request_id: str | None = None
    dashboard_id: str
    widget_type: GenerativeWidgetType
    data: list[dict[str, Any]] | str | None = None
    name: str | None = None
    description: str | None = None
    chart_params: dict[str, Any] | None = None
    inner_tab: str | None = None


class GetWorkspaceSnapshotCommand(Model):
    """Fetch the current workspace snapshot from the connected browser."""

    command: Literal["get_workspace_snapshot"]
    request_id: str | None = None


type WorkspaceCommand = Annotated[
    ReadWidgetCommand
    | CreateWidgetCommand
    | UpdateWidgetCommand
    | DeleteWidgetCommand
    | ManageNavigationBarCommand
    | AddGenerativeWidgetCommand
    | GetWorkspaceSnapshotCommand,
    Field(discriminator="command"),
]


class WorkspaceCommandResult(Model):
    """Typed browser command result returned through HTTP or MCP."""

    ok: bool
    command: str
    request_id: str | None = None
    message: str
    data: Any | None = None
    error: BridgeError | None = None


class BrowserCommandResultMessage(Model):
    """Browser-to-sidecar command result."""

    type: Literal["command_result"]
    result: WorkspaceCommandResult


class BrowserPing(Model):
    """Browser keepalive event."""

    type: Literal["ping"]


type BrowserMessage = Annotated[
    BrowserCommandResultMessage | BrowserPing,
    Field(discriminator="type"),
]


class SessionReadyEvent(Model):
    """Server-to-browser session confirmation."""

    type: Literal["session_ready"]
    session: BrowserSession


class CommandRequestEvent(Model):
    """Server-to-browser workspace command request."""

    type: Literal["command_request"]
    command: WorkspaceCommand


class ErrorEvent(Model):
    """Server-to-browser error payload."""

    type: Literal["error"]
    error: BridgeError


type ServerEvent = SessionReadyEvent | CommandRequestEvent | ErrorEvent

workspace_command_adapter = TypeAdapter(WorkspaceCommand)
browser_message_adapter = TypeAdapter(BrowserMessage)
