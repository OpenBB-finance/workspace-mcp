"""Runtime configuration for the Workspace MCP sidecar."""

import os
from dataclasses import dataclass

ENV_PREFIX = "OPENBB_WORKSPACE_MCP_"


def parse_csv(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated environment value into non-empty entries."""
    if not value:
        return ()
    return tuple(entry.strip() for entry in value.split(",") if entry.strip())


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
    cors_allow_origins: tuple[str, ...] = ()
    public_base_url: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables used by reload mode."""
        defaults = cls()
        return cls(
            host=os.getenv(f"{ENV_PREFIX}HOST", defaults.host),
            port=int(os.getenv(f"{ENV_PREFIX}PORT", str(defaults.port))),
            mcp_path=os.getenv(f"{ENV_PREFIX}MCP_PATH", defaults.mcp_path),
            health_path=os.getenv(f"{ENV_PREFIX}HEALTH_PATH", defaults.health_path),
            session_start_path=os.getenv(
                f"{ENV_PREFIX}SESSION_START_PATH", defaults.session_start_path
            ),
            websocket_path=os.getenv(
                f"{ENV_PREFIX}WEBSOCKET_PATH", defaults.websocket_path
            ),
            command_timeout_seconds=float(
                os.getenv(
                    f"{ENV_PREFIX}COMMAND_TIMEOUT_SECONDS",
                    str(defaults.command_timeout_seconds),
                )
            ),
            cors_allow_origins=parse_csv(os.getenv(f"{ENV_PREFIX}CORS_ALLOW_ORIGINS")),
        )

    @property
    def base_url(self) -> str:
        """Return the HTTP base URL for the current settings."""
        if self.public_base_url:
            return self.public_base_url.rstrip("/")
        return f"http://{self.host}:{self.port}"
