# OpenBB Workspace MCP

OpenBB Workspace Companion App that exposes the connected browser session as an MCP server.

What it does:

- exposes a stateless streamable HTTP MCP endpoint at `/mcp`
- forwards MCP tool calls to the connected Workspace tab over websocket
- returns fresh workspace snapshots and command results from the browser

Important security considerations:

- use only if you treat local MCP clients as trusted; they can read and mutate the connected Workspace
- do not expose the sidecar on `0.0.0.0`, a LAN, a tunnel, or a public reverse proxy
- `http` is fine for local deployments (`localhost`/`127.0.0.1`)

## How to use

### 1. Run

Run without cloning the repo:

```bash
curl -LsSf https://raw.githubusercontent.com/OpenBB-finance/workspace-mcp/main/scripts/run.sh | sh
```

Pass CLI options after `--`:

```bash
curl -LsSf https://raw.githubusercontent.com/OpenBB-finance/workspace-mcp/main/scripts/run.sh | sh -s -- --host 127.0.0.1 --port 8787
```

The script installs `uv` if needed, then runs `workspace-mcp` from the GitHub
source archive. To run a fork, branch, or local archive URL, set
`WORKSPACE_MCP_SOURCE`.

If `uv` is already installed, you can run the command directly:

```bash
uv tool run --python 3.13 --from https://github.com/OpenBB-finance/workspace-mcp/archive/refs/heads/main.zip workspace-mcp --host 127.0.0.1 --port 8787
```

For a persistent local install:

```bash
uv tool install --python 3.13 https://github.com/OpenBB-finance/workspace-mcp/archive/refs/heads/main.zip

# If installing from a PR
uv tool install --force --editable --python 3.13 .
```

Run:

```bash
workspace-mcp --host 127.0.0.1 --port 8787
```

By default, CORS allows `https://pro.openbb.co` and local loopback origins.
To allow another browser origin:

```bash
workspace-mcp --cors-allow https://example.openbb.dev
```

Repeat `--cors-allow` or pass comma-separated origins to allow more than one.

### 2. Connect from Workspace

- open OpenBB Workspace
- click the hamburger icon in the top left of the Workspace UI
- find `Workspace MCP Companion`
- set the companion base URL to your local sidecar URL, for example `http://127.0.0.1:8787`
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
- `manage_backends`
- `manage_apps`
- `assign_tasks_to_agents`
- `get_skill_content`

Scope:

- single user
- one connected Workspace browser session
- local-only sidecar
- flat tool list

## Development

Reload on code changes:

```bash
python -m workspace_mcp --host 127.0.0.1 --port 8787 --reload
```
