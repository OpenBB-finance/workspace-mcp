"""ASGI app tests for browser bridge HTTP behavior."""

from starlette.testclient import TestClient

from workspace_mcp.app import create_app


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
