---
name: openbb-app-builder
description: Build, review, debug, or extend OpenBB Workspace app backends, widgets.json, apps.json, widget parameters, dashboard layouts, and validation workflows. Use this for custom Workspace apps or converting HTTP APIs into Workspace widgets.
metadata:
  short-description: Build OpenBB Workspace apps
---

<!-- Generated from workspace_mcp/app_builder/resources by workspace_mcp/app_builder/skill_generator.py. Do not edit by hand. -->

# OpenBB App Builder

This installable skill is generated from the app-builder resource catalog in
`https://github.com/OpenBB-finance/workspace-mcp`. The MCP resources are the source of truth; this skill is only a
lightweight launcher for agents that support `npx skills add`.

## Preferred Path

When Workspace MCP is available, read the live MCP resource index first:

`openbb://workspace/app-builder/index`

Then follow the resource it routes you to. The live MCP resources should win
over this generated copy if they differ.

## Example Backends

For concrete backend implementations, templates, and widget examples, use:

`https://github.com/OpenBB-finance/backends-for-openbb`

Treat that repository as implementation context and examples. The canonical
app-builder instructions still live in the Workspace MCP resource catalog.

## Source Fallback

If MCP resources are unavailable, use the source resource files in GitHub.

| MCP resource | Source file |
|--------------|-------------|
| `openbb://workspace/app-builder/index` | [app-builder-index.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/app-builder-index.md) |
| `openbb://workspace/overview/what-is-workspace` | [overview/what-is-workspace.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/overview/what-is-workspace.md) |
| `openbb://workspace/overview/ai-agent-contract` | [overview/ai-agent-contract.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/overview/ai-agent-contract.md) |
| `openbb://workspace/contract/backend` | [backend-contract.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/backend-contract.md) |
| `openbb://workspace/specs/widgets-json` | [specs/widgets-json.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/specs/widgets-json.md) |
| `openbb://workspace/specs/apps-json` | [specs/apps-json.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/specs/apps-json.md) |
| `openbb://workspace/specs/widget-types` | [specs/widget-types.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/specs/widget-types.md) |
| `openbb://workspace/specs/widget-parameters` | [specs/widget-parameters.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/specs/widget-parameters.md) |
| `openbb://workspace/specs/layout-grid` | [specs/layout-grid.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/specs/layout-grid.md) |
| `openbb://workspace/guides/build-an-app` | [guides/build-an-app.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/guides/build-an-app.md) |
| `openbb://workspace/guides/review-app` | [guides/review-app.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/guides/review-app.md) |
| `openbb://workspace/guides/debug-app` | [guides/debug-app.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/guides/debug-app.md) |
| `openbb://workspace/guides/convert-endpoint-to-widget` | [guides/convert-endpoint-to-widget.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/guides/convert-endpoint-to-widget.md) |
| `openbb://workspace/examples/generic-http/minimal` | [examples/generic-http-minimal.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/examples/generic-http-minimal.md) |
| `openbb://workspace/examples/python-fastapi/minimal` | [examples/python-fastapi-minimal.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/examples/python-fastapi-minimal.md) |
| `openbb://workspace/validation/common-errors` | [validation/common-errors.md](https://github.com/OpenBB-finance/workspace-mcp/blob/main/workspace_mcp/app_builder/resources/validation/common-errors.md) |
