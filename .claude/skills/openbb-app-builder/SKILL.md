---
name: openbb-app-builder
description: Build, review, debug, or extend OpenBB Workspace app backends, widgets.json, apps.json, widget parameters, dashboard layouts, and validation workflows. Use this for custom Workspace apps or converting HTTP APIs into Workspace widgets.
metadata:
  short-description: Build OpenBB Workspace apps
---

<!-- Generated from workspace_mcp/app_builder/resources by workspace_mcp/app_builder/skill_generator.py. Do not edit by hand. -->

# OpenBB App Builder

This installable skill is generated from the app-builder resource catalog in
`https://github.com/OpenBB-finance/workspace-mcp`. The MCP resources are the source of truth; this skill is an
offline compatibility package for agents that support `npx skills add`.

## Preferred Path

When Workspace MCP is available, read the live MCP resource index first:

`openbb://workspace/app-builder/index`

Then follow the resource it routes you to. The live MCP resources should win
over this generated copy if they differ.

## Offline Fallback

If MCP resources are unavailable, use the generated references bundled with
this skill. They mirror the registered Workspace MCP resources at generation
time.

| MCP resource | Bundled reference |
|--------------|-------------------|
| `openbb://workspace/app-builder/index` | `references/app-builder-index.md` |
| `openbb://workspace/overview/what-is-workspace` | `references/overview/what-is-workspace.md` |
| `openbb://workspace/overview/ai-agent-contract` | `references/overview/ai-agent-contract.md` |
| `openbb://workspace/contract/backend` | `references/backend-contract.md` |
| `openbb://workspace/specs/widgets-json` | `references/specs/widgets-json.md` |
| `openbb://workspace/specs/apps-json` | `references/specs/apps-json.md` |
| `openbb://workspace/specs/widget-types` | `references/specs/widget-types.md` |
| `openbb://workspace/specs/widget-parameters` | `references/specs/widget-parameters.md` |
| `openbb://workspace/specs/layout-grid` | `references/specs/layout-grid.md` |
| `openbb://workspace/guides/build-an-app` | `references/guides/build-an-app.md` |
| `openbb://workspace/guides/review-app` | `references/guides/review-app.md` |
| `openbb://workspace/guides/debug-app` | `references/guides/debug-app.md` |
| `openbb://workspace/guides/convert-endpoint-to-widget` | `references/guides/convert-endpoint-to-widget.md` |
| `openbb://workspace/examples/generic-http/minimal` | `references/examples/generic-http-minimal.md` |
| `openbb://workspace/examples/python-fastapi/minimal` | `references/examples/python-fastapi-minimal.md` |
| `openbb://workspace/validation/common-errors` | `references/validation/common-errors.md` |
