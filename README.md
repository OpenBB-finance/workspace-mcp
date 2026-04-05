# OpenBB Workspace MCP

Local Python 3.13+ sidecar that exposes a connected OpenBB Workspace browser session as an MCP server.

What it does:

- exposes a stateless streamable HTTP MCP endpoint at `/mcp`
- accepts a localhost browser session at `/bridge/session/start` and `/bridge/ws`
- forwards MCP tool calls to the connected Workspace tab over websocket
- returns fresh workspace snapshots and command results from the browser

Current MCP surface:

- `get_workspace_snapshot`
- `get_widget_data`
- `get_extra_widget_data`
- `get_params_options`
- `read_widget`
- `create_widget`
- `add_widget_to_dashboard`
- `update_widget`
- `update_widget_in_dashboard`
- `delete_widget`
- `manage_navigation_bar`
- `add_generative_widget`
- `assign_tasks_to_agents`
- `execute_agent_tool`
- `get_skill_content`

Run locally:

```bash
python -m workspace_mcp --host 127.0.0.1 --port 8787
```

Reload on code changes:

```bash
python -m workspace_mcp --host 127.0.0.1 --port 8787 --reload
```

Practical usage rules:

- call `get_workspace_snapshot` first
- use snake_case payloads
- for widget data calls, use `data_sources` items shaped like `{origin, widget_id, data_args, widget_uuid?, ssm_request?}`
- for parameter option calls, use `param_options_queries` items shaped like `{origin, widget_id, param_name, data_args}`
- omit `dashboard_id` to target the current dashboard route
- do not invent placeholder dashboard ids like `active_dashboard`, `current_dashboard`, `null`, or `undefined`
- `create_widget`, `update_widget`, `delete_widget`, `manage_navigation_bar`, and `add_generative_widget` operate on existing dashboards only
- `manage_navigation_bar` manages the `navigation_bar` widget on an existing dashboard; if it does not exist yet, call `create` first
- prefer `widget_uuid` for widget instance operations; `widget_id` is only a fallback when there is exactly one matching instance on the target dashboard

Current scope:

- localhost only
- one connected Workspace browser session
- flat tool list only
- exploration mode deferred
