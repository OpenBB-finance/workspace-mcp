"""CLI tests for the Workspace MCP launcher."""

import os

from workspace_mcp import __main__


def test_main_uses_import_string_when_reload_is_enabled(
    monkeypatch,
) -> None:
    """Reload mode should use an import string so Uvicorn can re-create the app."""
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(target: object, **kwargs: object) -> None:
        calls.append((target, kwargs))

    monkeypatch.setattr(__main__.uvicorn, "run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        ["workspace-mcp", "--host", "127.0.0.1", "--port", "8789", "--reload"],
    )

    __main__.main()

    assert calls == [
        (
            "workspace_mcp.app:create_app",
            {
                "host": "127.0.0.1",
                "port": 8789,
                "reload": True,
                "factory": True,
            },
        )
    ]
    assert os.environ["OPENBB_WORKSPACE_MCP_PORT"] == "8789"
    assert os.environ["OPENBB_WORKSPACE_MCP_HOST"] == "127.0.0.1"


def test_main_sets_custom_cors_origins_for_reload(monkeypatch) -> None:
    """Reload mode should pass custom CORS origins through the environment."""
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(target: object, **kwargs: object) -> None:
        calls.append((target, kwargs))

    monkeypatch.setattr(__main__.uvicorn, "run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "workspace-mcp",
            "--reload",
            "--cors-allow",
            "https://one.example, https://two.example",
            "--cors-allow",
            "http://localhost:3000",
        ],
    )

    __main__.main()

    assert len(calls) == 1
    assert os.environ["OPENBB_WORKSPACE_MCP_CORS_ALLOW_ORIGINS"] == (
        "https://one.example,https://two.example,http://localhost:3000"
    )


def test_main_uses_app_instance_without_reload(monkeypatch) -> None:
    """Normal mode should boot the already-constructed app object."""
    calls: list[tuple[object, dict[str, object]]] = []

    def fake_run(target: object, **kwargs: object) -> None:
        calls.append((target, kwargs))

    monkeypatch.setattr(__main__.uvicorn, "run", fake_run)
    monkeypatch.setattr("sys.argv", ["workspace-mcp", "--port", "8790"])

    __main__.main()

    assert len(calls) == 1
    target, kwargs = calls[0]
    assert callable(target)
    assert kwargs == {"host": "127.0.0.1", "port": 8790}


def test_main_passes_custom_cors_origins_without_reload(monkeypatch) -> None:
    """Normal mode should construct the app with custom CORS origins."""
    calls: list[tuple[object, dict[str, object]]] = []
    settings_seen = []
    app = object()

    def fake_create_app(settings: object) -> object:
        settings_seen.append(settings)
        return app

    def fake_run(target: object, **kwargs: object) -> None:
        calls.append((target, kwargs))

    monkeypatch.setattr(__main__, "create_app", fake_create_app)
    monkeypatch.setattr(__main__.uvicorn, "run", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        ["workspace-mcp", "--cors-allow", "https://workspace.example"],
    )

    __main__.main()

    assert len(settings_seen) == 1
    assert settings_seen[0].cors_allow_origins == ("https://workspace.example",)
    assert calls == [(app, {"host": "127.0.0.1", "port": 8787})]
