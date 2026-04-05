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
