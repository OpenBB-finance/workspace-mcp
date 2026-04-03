# OpenBB Workspace MCP

Python 3.13+ sidecar that exposes a connected OpenBB Workspace browser session as a FastMCP server.

Current design:

- the sidecar keeps only session and in-flight request state
- workspace state is fetched reactively from the browser when requested
- the browser remains the source of truth for snapshots and command execution
- bridge-local models handle sessions, websocket events, and command envelopes
- canonical workspace payloads reuse `openbb_ai.models.WorkspaceState` and `AgentTool`

Runtime surfaces:

- streamable HTTP MCP endpoint at `/mcp`
- browser session bootstrap endpoint at `/bridge/session/start`
- browser websocket bridge at `/bridge/ws`
- health endpoint at `/health`

Current implementation slice:

- end-to-end browser bridge works for:
  - explicit browser connect from Workspace UI
  - `get_workspace_snapshot`
  - `create_widget`
- the browser bridge now handles:
  - CORS preflight for `POST /bridge/session/start`
  - websocket session bootstrap and keepalive
  - MCP client calls that send `wait_for_previous`
- if Workspace has no active dashboard, `get_workspace_snapshot` returns
  `current_dashboard_uuid = null` and exposes only global/available context

Current flat MCP server surface:

- `get_workspace_snapshot`
- `read_widget`
- `create_widget`
- `update_widget`
- `delete_widget`
- `manage_navigation_bar`
- `add_generative_widget`

Current limitation:

- the Python sidecar exposes the full flat v1 tool list, but the current
  `terminalpro` browser bridge slice only dispatches `get_workspace_snapshot`
  and `create_widget`
- the next frontend slice is to add browser handlers for:
  - `read_widget`
  - `update_widget`
  - `delete_widget`
  - `manage_navigation_bar`
  - `add_generative_widget`

Run locally:

```bash
python -m workspace_mcp --host 127.0.0.1 --port 8787
```
