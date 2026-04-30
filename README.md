# OpenBB Workspace MCP

OpenBB Workspace Companion App that exposes the connected browser session as an MCP server.

What it does:

- exposes a stateless streamable HTTP MCP endpoint at `/mcp`
- forwards MCP tool calls to the connected Workspace tab over websocket
- returns fresh workspace snapshots and command results from the browser

## How to use

### 1. Install & Run

Install:

```bash
uv tool install --python 3.13 git+https://github.com/OpenBB-finance/workspace-mcp.git

# If installing from a PR
uv tool install --force --editable --python 3.13 .
```

Run:

```bash
workspace-mcp --host 127.0.0.1 --port 8787
```

### 2. Connect from Workspace

- open OpenBB Workspace
- go to the AI Agents tab
- find `Workspace MCP Companion`
- set the companion base URL to your sidecar URL, for example `http://127.0.0.1:8787` for local or `https://mcp.example.com` for a remote deployment
- connect the companion after the sidecar is running

### 3. Connect your AI agent

Use the `http://127.0.0.1:8787/mcp` as the MCP url that you pass into the `mcp add` command of your agent.

Example `.mcp.json` for claude code:

```json
{
  "mcpServers": {
    "workspace_mcp": {
      "type": "http",
      "url": "http://127.0.0.1:8787/mcp"
    }
  }
}
```

## Features

MCP tools:

- `get_workspace_snapshot`
- `list_available_widgets`
- `get_widget_schema`
- `get_widget_data`
- `get_params_options`
- `manage_dashboard`
- `navigate_workspace`
- `update_widget_layout`
- `read_widget`
- `create_widget`
- `update_widget`
- `delete_widget`
- `manage_navigation_bar`
- `add_generative_widget`
- `assign_tasks_to_agents`
- `get_skill_content`

Scope:

- single user
- one connected Workspace browser session
- flat tool list

Browser security:

- `http` is fine for local deployments (`localhost`/`127.0.0.1`)
- for any non-local deployment, use `https`; browsers will block insecure `http` sidecar requests from a secure Workspace origin

## Development

Reload on code changes:

```bash
python -m workspace_mcp --host 127.0.0.1 --port 8787 --reload
```
