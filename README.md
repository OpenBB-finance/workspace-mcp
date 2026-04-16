# OpenBB Workspace MCP

Local Python 3.13+ sidecar that exposes a connected OpenBB Workspace browser session as an MCP server.

What it does:

- exposes a stateless streamable HTTP MCP endpoint at `/mcp`
- accepts a localhost browser session at `/bridge/session/start` and `/bridge/ws`
- forwards MCP tool calls to the connected Workspace tab over websocket
- returns fresh workspace snapshots and command results from the browser

Current MCP surface:

- `get_workspace_snapshot`
- `list_available_widgets`
- `get_widget_schema`
- `get_widget_data`
- `get_params_options`
- `create_dashboard`
- `read_dashboard`
- `update_dashboard`
- `update_dashboard_layout`
- `read_widget`
- `create_widget`
- `update_widget`
- `delete_widget`
- `manage_navigation_bar`
- `add_generative_widget`
- `assign_tasks_to_agents`
- `execute_agent_tool`
- `get_skill_content`

Authoring support:

- widget discovery is available through `list_available_widgets` and `get_widget_schema`
- dashboard creation and rename are available through `create_dashboard` and `update_dashboard`
- dashboard composition can be inspected through `get_workspace_snapshot` and `read_dashboard`
- visible widget placement is controlled through `update_dashboard_layout`
- dashboard tabs remain managed through `manage_navigation_bar`
- `update_widget` is limited to widget-instance config changes

Run locally:

```bash
python -m workspace_mcp --host 127.0.0.1 --port 8787
```

Reload on code changes:

```bash
python -m workspace_mcp --host 127.0.0.1 --port 8787 --reload
```

Current scope:

- localhost only
- one connected Workspace browser session
- flat tool list only
- exploration mode deferred
