# OpenBB Workspace MCP

Connect an AI agent to your active OpenBB Workspace browser session.

This runs a local MCP sidecar at `http://127.0.0.1:8787/mcp`. OpenBB Workspace connects to the sidecar from your browser, and your AI agent connects to the MCP endpoint.

## Quick Start

Requires `uv`. Install it from the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/), or use the [bootstrap command](#bootstrap-scripts) below.

### 1. Install the command

Install `workspace-mcp` from the GitHub source archive:

```bash
uv tool install --python 3.13 https://github.com/OpenBB-finance/workspace-mcp/archive/refs/heads/main.zip
```

### 2. Start the sidecar

```bash
workspace-mcp
```

The sidecar starts on `http://127.0.0.1:8787`.

### 3. Connect OpenBB Workspace

1. Open OpenBB Workspace.
2. Click the hamburger icon in the top-left corner.
3. Open `Workspace MCP Companion`.
4. Set the companion base URL to:

```text
http://127.0.0.1:8787
```

5. Connect the companion.

### 4. Connect Your Agent

Use this MCP URL in your agent:

```text
http://127.0.0.1:8787/mcp
```

Example `.mcp.json`:

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

## Common Options

Run on a different host or port:

```bash
workspace-mcp --host 127.0.0.1 --port 8787
```

Allow another browser origin:

```bash
workspace-mcp --cors-allow https://example.openbb.dev
```

Repeat `--cors-allow` or pass comma-separated origins to allow more than one.

## Security

Only run this locally.

Connected MCP clients can read and change the active Workspace session. Do not expose the sidecar on `0.0.0.0`, a LAN, a tunnel, or a public reverse proxy.

Local `http` is expected for `localhost` and `127.0.0.1`.

## Capabilities

The MCP server lets agents:

- inspect the current Workspace state
- read, create, update, move, and delete widgets
- navigate Workspace pages and dashboards
- manage dashboard layout and navigation
- inspect available widgets and widget schemas
- read Workspace app-building documentation
- manage Workspace backends and apps
- assign tasks to connected agents

## Bootstrap Scripts

The repo includes scripts that install `uv` if needed, then run `workspace-mcp` from the GitHub source archive.

macOS, Linux, WSL, and Git Bash:

```bash
curl -LsSf https://raw.githubusercontent.com/OpenBB-finance/workspace-mcp/main/scripts/run.sh | sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -Command "Invoke-RestMethod https://raw.githubusercontent.com/OpenBB-finance/workspace-mcp/main/scripts/run.ps1 | Invoke-Expression"
```

Pass CLI options after `--`.

macOS, Linux, WSL, and Git Bash:

```bash
curl -LsSf https://raw.githubusercontent.com/OpenBB-finance/workspace-mcp/main/scripts/run.sh | sh -s -- --host 127.0.0.1 --port 8787
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -Command "& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/OpenBB-finance/workspace-mcp/main/scripts/run.ps1'))) --host 127.0.0.1 --port 8787"
```

To run a fork, branch, or local archive URL with these scripts, set `WORKSPACE_MCP_SOURCE`.

## Development

From a local checkout:

```bash
uv run python -m workspace_mcp --host 127.0.0.1 --port 8787 --reload
```

For an editable local install:

```bash
uv tool install --force --editable --python 3.13 .
```