"""Runtime configuration for the Workspace MCP sidecar."""

from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    """Configuration for the MCP and browser bridge HTTP surfaces."""

    host: str = "127.0.0.1"
    port: int = 8787
    mcp_path: str = "/mcp"
    health_path: str = "/health"
    session_start_path: str = "/bridge/session/start"
    websocket_path: str = "/bridge/ws"
    command_timeout_seconds: float = 15.0

    @property
    def base_url(self) -> str:
        """Return the HTTP base URL for the current settings."""
        return f"http://{self.host}:{self.port}"
