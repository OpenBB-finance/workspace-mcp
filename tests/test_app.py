"""ASGI app tests for browser bridge HTTP behavior."""

from starlette.testclient import TestClient

from workspace_mcp.app import create_app
from workspace_mcp.config import Settings


def test_bridge_session_start_options_preflight() -> None:
    """Browser session bootstrap should accept localhost CORS preflight."""
    app = create_app()

    with TestClient(app) as client:
        response = client.options(
            "/bridge/session/start",
            headers={
                "Origin": "http://127.0.0.1:1420",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:1420"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_bridge_session_start_options_preflight_with_custom_cors_origin() -> None:
    """Custom configured CORS origins should be allowed."""
    app = create_app(Settings(cors_allow_origins=("https://example.openbb.dev",)))

    with TestClient(app) as client:
        response = client.options(
            "/bridge/session/start",
            headers={
                "Origin": "https://example.openbb.dev",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://example.openbb.dev"
    )
    assert "POST" in response.headers["access-control-allow-methods"]


def test_mcp_streamable_http_is_stateless() -> None:
    """The MCP endpoint should not depend on sticky FastMCP session IDs."""
    app = create_app()

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "mcp-session-id": "stale-session-id",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.1"},
                },
            },
        )

    assert response.status_code == 200
    assert "Session not found" not in response.text
