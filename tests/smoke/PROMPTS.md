# MCP Smoke-Test Prompts

A walkthrough of natural-language prompts that exercise the Workspace MCP tool surface end-to-end. Each scenario lists the prompt, the rough tool sequence the LLM should pick, the deterministic end-state to verify, and the regression each scenario is the net for.

This file is a **manual procedure** today — drive it yourself by giving an LLM these prompts in order while it has the MCP attached, then verify end-state via `get_workspace_snapshot`. Later this same file can be the source of truth for an automated runner (`scripts/smoke.py`) and for a `tests/test_smoke_scenarios.py` that exercises the same flows via direct `call_tool` (no LLM).

---

## How to run

### 1. Start the sidecar

```bash
cd workspace-mcp
.venv/Scripts/python.exe -m workspace_mcp --host 127.0.0.1 --port 8787
```

The sidecar listens on `http://127.0.0.1:8787/mcp` (streamable HTTP). Health check: `curl http://127.0.0.1:8787/health`.

### 2. Open Workspace and connect the MCP Companion

Workspace runs at `https://pro.openbb.co` (production), `https://pro.openbb.dev` (staging), or `http://localhost:1420` (local dev). The MCP Companion is a side panel inside Workspace that bridges the running browser session to the sidecar.

The Companion entry is gated by the `VITE_UI_SHOW_COMPANION_MODE` flag (see `terminalpro/.env`). Make sure it's `"true"` for the build you're testing against, then open it from the hamburger menu and connect to `http://127.0.0.1:8787`.

Once connected, the sidecar's WebSocket gets a session and tools start working. `get_workspace_snapshot` should return your current dashboard state.

### 3. Drive an LLM with the prompts

Point any MCP-aware client (Claude Desktop, Claude Code, Cursor) at the sidecar, then paste prompts from the scenarios below in order. After each scenario, run the **Verify by** step to confirm end-state.

### 4. What you're looking for

- **Tool selection**: did the LLM pick a tool from the expected sequence? Some shuffle is fine; gross deviation (calling the wrong family of tool) is a finding.
- **End state**: the *Expected end state* check is the source of truth. If the LLM got there via a different tool path, that's still a pass.
- **Regression callouts**: each scenario flags a specific contract that has historically been a foot-gun. Watch for those.

---

## Conventions used in scenarios

- **Setup** — preconditions for the scenario (active dashboard, registered backend, etc.). If the previous scenario left the right setup, you can chain.
- **Prompt** — verbatim text to give the LLM.
- **Expected tool sequence** — tolerant; alternates noted with `OR`.
- **Expected end state** — deterministic check, the scenario's pass condition.
- **Verify by** — the tool call(s) you (or the LLM) make to confirm end-state.
- **Watch for** — the specific regression this scenario is the net for. If you see it, the test failed even if end-state looked OK.

Scenarios are independent unless one explicitly chains to another. **Scenarios 1–6 chain** — they build a single dashboard. **Scenarios 7+ are standalone** unless noted.

---

## 1. Create a fresh dashboard

**What this exercises**: `manage_dashboard` create, dashboard activation, snapshot context tracking.

**Setup**: Workspace open, MCP Companion connected. Any dashboard.

**Prompt**:
> Create a new dashboard called "MCP Smoke Test" and switch to it.

**Expected tool sequence**:
1. `manage_dashboard` operation=create, name="MCP Smoke Test", activate=true (default)

**Expected end state**:
- A new dashboard exists with that name.
- Workspace's current route is on it.
- `current_dashboard_uuid` in subsequent snapshots points to the new dashboard.

**Verify by**:
- `get_workspace_snapshot` → `workspace_state.current_dashboard_uuid` matches the dashboard returned by step 1.

**Watch for**:
- LLM matching dashboards by **name** instead of UUID (regression — duplicates with the same name are common; identification must be by UUID).

---

## 2. Add a navigation bar with two tabs

**What this exercises**: `manage_navigation_bar` create, the typed `tabs: list[NavigationTabInput]` migration (Round 1), the `{name: str}` shape that rejects `tab_id`/`tab_name`.

**Setup**: continues from #1.

**Prompt**:
> Add two tabs to this dashboard: "Overview" and "Charts".

**Expected tool sequence**:
1. `manage_navigation_bar` operation=create OR add_tabs, tabs=[{name: "Overview"}, {name: "Charts"}]

**Expected end state**:
- Dashboard has two tabs named "Overview" and "Charts".
- Generated `tab_id` slugs are `overview` and `charts`.

**Verify by**:
- `manage_dashboard` operation=read → response includes both tab_ids in dashboard_composition.

**Watch for** (Round 1 regression):
- LLM passing `tabs: ["Overview", "Charts"]` (string array) — should now fail at the pydantic boundary.
- LLM passing `tabs: [{tab_id: "overview", name: "Overview"}]` — should fail at the pydantic `extra="forbid"` boundary.
- LLM passing `tabs: [{name: ""}]` — should fail the `_name_must_be_non_blank` validator.

---

## 3. Navigate to a tab and add a generative note

**What this exercises**: `navigate_workspace` operation=tab, the new-tab → navigate → add-content workflow, `add_generative_widget` with `widget_type="note"` and raw-string `data` (Round 2 typed input).

**Setup**: continues from #2.

**Prompt**:
> Switch to the Overview tab and put a markdown note on it that says: "# Smoke Test — running scenarios".

**Expected tool sequence**:
1. `navigate_workspace` operation=tab, tab_id="overview"
2. `add_generative_widget` widget_type=note, data="# Smoke Test — running scenarios" (raw string, not stringified JSON), no `inner_tab` (the active tab handles placement)

**Expected end state**:
- Overview tab has 1 widget, type=note, with the markdown body.

**Verify by**:
- `manage_dashboard` operation=read → Overview tab's layout shows one widget; `read_widget` on its uuid returns the markdown body.

**Watch for**:
- LLM trying to use `create_widget` with `widget_id="rich_note"` — must return invalid_request and route the LLM back to `add_generative_widget`.
- LLM passing `inner_tab="overview"` *thinking* it creates the tab — `inner_tab` only places on an existing tab. The new-tab workflow (add_tabs → navigate → add) is the right one.

---

## 4. Generative chart widget — camelCase regression

**What this exercises**: `add_generative_widget` with `widget_type="chart"` and the structured `chart_params` migration (Round 1, the only one where the wire shape is camelCase). **This scenario is the regression net for the camelCase preservation fix.**

**Setup**: continues from #3.

**Prompt**:
> Switch to the Charts tab and add a bar chart of quarterly revenue: Q1=100, Q2=140, Q3=160, Q4=210.

**Expected tool sequence**:
1. `navigate_workspace` operation=tab, tab_id="charts"
2. `add_generative_widget` widget_type=chart, data=[{quarter: "Q1", revenue: 100}, ...] (passed as a JSON array, not a stringified JSON literal), chart_params={chartType: "bar", xKey: "quarter", yKey: ["revenue"]}

**Expected end state**:
- Charts tab has 1 chart widget rendering the 4 quarters as bars.

**Verify by**:
- `manage_dashboard` operation=read → Charts tab has one widget.
- Inspect the widget — it should render. If it renders blank or errors, the chart_params keys may have arrived as snake_case.

**Watch for** (the migration's headline regression):
- `chart_params` arriving on the bridge as snake_case (`chart_type`, `x_key`, `y_key`) — frontend Zod (`ai.ts`) rejects this and the chart silently fails to render.
- LLM passing `chart_params: {chartType: "bar"}` without `yKey` — should fail `validate_add_generative_widget_request`.

---

## 5. Read the dashboard composition

**What this exercises**: `manage_dashboard` operation=read OR `get_workspace_snapshot.dashboard_composition`. Both surface the same shape.

**Setup**: continues from #4.

**Prompt**:
> What's on this dashboard right now?

**Expected tool sequence**:
1. `get_workspace_snapshot` (preferred when starting a session) OR `manage_dashboard` operation=read

**Expected end state**:
- LLM's response describes: 2 tabs, Overview with 1 note widget, Charts with 1 chart widget.

**Verify by**:
- The LLM's summary matches what you put there in #2–4.

**Watch for**:
- LLM calling `get_workspace_snapshot` repeatedly across consecutive turns when nothing changed — guidance says to reuse `current_dashboard_uuid` from the previous response and only re-snapshot after navigation.

---

## 6. Move and resize a widget

**What this exercises**: `update_widget_layout` (note: tool is named `update_widget_layout` but emits bridge command `update_dashboard_layout` — unresolved naming inconsistency from the review). 40-column grid math.

**Setup**: continues from #5.

**Prompt**:
> Make the bar chart half width

**Expected tool sequence**:
1. `manage_dashboard` operation=read OR `get_workspace_snapshot` to find the chart's `widget_uuid`
2. `update_widget_layout` widget_uuid=<chart>, x=0, y=2 (below nav bar) or y=0, w=20, h=12-ish

**Expected end state**:
- Chart widget spans the 20-column width.

**Verify by**:
- `manage_dashboard` operation=read → layout shows w=20 for the chart.

**Watch for**:
- LLM trying `update_widget` with layout fields (`x`, `y`, `w`, `h`, `gridData`) — guarded by `has_layout_ui_args`; should return invalid_request.
- LLM placing the widget at y=0 when a navigation_bar occupies y=0 — minor; the grid will resolve, but guidance says first content row usually starts at y=2.
- LLM using **widget title** ("the bar chart") as a layout identifier — must be widget_uuid (or widget_id when only one instance exists).

---

## 7. Discover widgets from a connected backend

**What this exercises**: `list_available_widgets` (with and without filter), `get_widget_schema`, `get_params_options` when a param requires lookup.

**Setup**: At least one backend already connected to Workspace. Use whichever is registered (an OpenBB-shipped one or your own). For deterministic flow, prefer one with ~5 widgets so the catalog stays readable.

**Prompt**:
> What widgets does the **<backend name>** backend have? Pick one with a parameter and show me what it expects.

**Expected tool sequence**:
1. `list_available_widgets` origin="<backend name>" (filtered)
2. `get_widget_schema` origin="<backend name>", widget_id=<one from list>
3. If the schema returns `requires_options_lookup=true` on any param: `get_params_options` for that param.

**Expected end state**:
- LLM's response names the widgets and describes one widget's params with concrete option values when applicable.

**Verify by**:
- The `origin` and `widget_id` strings the LLM names should match exactly what `list_available_widgets` returned.

**Watch for**:
- LLM **inventing identifiers** instead of using ones from `list_available_widgets`.
- LLM calling `get_params_options` on a param whose schema didn't have `requires_options_lookup=true` (wasted call).
- `rich_note` appearing in the catalog list — it should be filtered out (generative-only).

---

## 8. Create a regular widget on a dashboard

**What this exercises**: full discovery → create flow with the Round 2 typed `data_args: dict[str, Any]` input.

**Setup**: an active dashboard, a backend with at least one parametric widget.

**Prompt**:
> Add the **<widget name>** widget from **<backend name>** to this dashboard with **<param>** = **<value>**.

**Expected tool sequence**:
1. `list_available_widgets` to confirm origin/widget_id
2. `get_widget_schema` for the param shape
3. `create_widget` origin=<...>, widget_id=<...>, data_args={"<param>": "<value>"}

**Expected end state**:
- Widget appears on the active dashboard with the supplied param applied.

**Verify by**:
- `read_widget` on the new widget's uuid returns config with the data_args echoed back.

**Watch for** (Round 2 regression):
- LLM still passing `data_args_json` as a stringified JSON object — should now fail at the pydantic boundary because that param no longer exists.

**Watch for**:
- LLM passing `data_args_json` as an unescaped object instead of a stringified JSON — currently rejected; this scenario will become trivial after Round 2 (typed `data_args: dict[str, Any]`).
- LLM omitting `origin` — current pass-through requires both origin and widget_id.

---

## 9. Add a backend with structured `endpoint_headers`

**What this exercises**: `manage_backends` operation=add, the typed `endpoint_headers: list[BackendEndpointHeader]` migration (Round 1), the `location` enum (`headers` | `query`) defaulting to `"headers"`.

**Setup**: A reachable HTTP backend serving `/widgets.json` (a tiny FastAPI demo, the upcoming `tests/fixtures/sample_backend/`, or any of OpenBB's example backends from `backends-for-openbb`).

**Prompt**:
> Add **<URL>** as a backend called "Smoke Test Backend", and send an `X-Auth-Token` header with value `smoke-test`.

**Expected tool sequence**:
1. `manage_backends` operation=add, name="Smoke Test Backend", url=<URL>, endpoint_headers=[{key: "X-Auth-Token", value: "smoke-test"}]

**Expected end state**:
- Backend appears in `manage_backends` operation=list.
- Subsequent `list_available_widgets backend_id=<new id>` returns the backend's widgets.

**Verify by**:
- `manage_backends` operation=list → entry with the right name and url; widget_count > 0 if the backend exposes any.

**Watch for** (Round 1 regression):
- `endpoint_headers` arriving on the bridge as a stringified JSON instead of a real array.
- `location` field omitted entirely — should default to `"headers"` per `BackendEndpointHeader.location` and frontend's `?? "headers"` fallback.
- LLM passing camelCase `{Key, Value, Location}` — should fail pydantic (`extra="forbid"` rejects unknown keys).

---

## 10. Instantiate an app template

**What this exercises**: `manage_apps` operation=list → instantiate, the dashboard-from-template route.

**Setup**: a connected backend that ships an `apps.json` with at least one template (the OpenBB demo backends do).

**Prompt**:
> What apps does **<backend name>** offer? Open the first one as a new dashboard.

**Expected tool sequence**:
1. `manage_apps` operation=list, backend_id=<from manage_backends>
2. `manage_apps` operation=instantiate, backend_id=<...>, app_name=<first app's name> (activate=true default)

**Expected end state**:
- A new dashboard exists, populated with widgets and tabs from the app template.
- Workspace's current route switches to the new dashboard.

**Verify by**:
- `get_workspace_snapshot.dashboard_composition` after instantiation shows the templated layout.

**Watch for**:
- LLM passing `app_name` AND `template_id` together — fine, but only one is required.
- LLM trying to use `manage_dashboard` operation=create and then re-creating widgets manually instead of `manage_apps` instantiate — slower path, possible LLM mistake.

---

## 11. Delegate a task to a configured agent

**What this exercises**: `assign_tasks_to_agents` with the typed `task_requests: list[TaskRequest]` (Round 1). Tests snake_case wire shape end-to-end.

**Setup**: at least one external agent configured in Workspace (`agents` settings panel).

**Prompt**:
> Send this task to **<agent name>**: review the dashboard and flag any anomalies in the chart.

**Expected tool sequence**:
1. `get_workspace_snapshot` to find the agent's `holder_url` and `agent_id`
2. `assign_tasks_to_agents` task_requests=[{id: <generated>, description: "review the dashboard...", assigned_holder_url: "<...>", assigned_agent_id: "<...>"}]

**Expected end state**:
- Task appears in the agent's queue (visible in the Workspace UI).

**Verify by**:
- Open the agent's task panel in Workspace.
- The agent eventually responds (timing varies).

**Watch for** (Round 1 regression):
- `task_requests` field names arriving on the bridge as **camelCase** (`assignedHolderUrl`, `assignedAgentId`) — should be snake_case to match the frontend Zod schema.
- LLM omitting `id` — pydantic now rejects it (the field is required on `TaskRequest`).
- LLM inventing a `holder_url` instead of pulling from snapshot — a finding (it should look at snapshot.tools or snapshot.agents).

---

## 12. Pull live widget data

**What this exercises**: `get_widget_data` — the same data path the renderer hits. For chart widgets, also pins the `raw=true` convention that turns Plotly figures into rows. Run twice — once on a `table`/`metric` widget, once on a `chart`.

**Setup**: a dashboard with at least one data-bearing widget.

### 12a — table or metric widget

**Prompt**:
> What data is the **<table widget name>** showing right now?

**Expected tool sequence**:
1. `get_workspace_snapshot` OR `manage_dashboard` operation=read to find origin + widget_id
2. `get_widget_data` origin=<...>, widget_id=<...>, widget_uuid=<...>, data_args=<current params>

**Expected end state**:
- LLM responds with rows or metrics from the widget's current state.

**Verify by**:
- The numbers/strings the LLM cites should match what's visible in the widget UI.

### 12b — chart widget (raw=true regression net)

**Prompt**:
> What's in the **<chart widget name>** — pull the underlying data, not the chart figure.

**Expected tool sequence**:
1. `get_workspace_snapshot` OR `manage_dashboard` operation=read
2. `get_widget_data` origin=<...>, widget_id=<...>, widget_uuid=<...>, **data_args={"raw": true, ...current params}**

**Expected end state**:
- Tool response carries an array-of-rows shape (`[{date: ..., value: ...}, ...]`).
- LLM's answer cites concrete row values, not "the chart shows a line going up."

**Watch for**:
- LLM omitting `raw=true` in `data_args` and getting back `{data: [...], layout: {...}}` (Plotly figure) — that's the failure mode. Both the `get_widget_data` tool description and `DATA_SOURCE_SHAPE` in `SERVER_INSTRUCTIONS` now call this out; if the LLM still misses it, the description needs sharpening.
- Backend chart endpoints that don't accept `raw=true` at all — that's a backend-contract bug (every chart endpoint should support it per `openbb://workspace/guides/convert-endpoint-to-widget`). Skip this scenario for that backend until it's fixed.

---

## 13. Cleanup — delete a widget

**What this exercises**: `delete_widget` with `widget_uuid` resolution. Also serves as cleanup after running the chain.

**Setup**: an active dashboard with widgets to remove (e.g. after scenarios 1–6).

**Prompt**:
> Delete the bar chart from this dashboard.

**Expected tool sequence**:
1. `manage_dashboard` operation=read OR `get_workspace_snapshot` to find the chart's `widget_uuid`
2. `delete_widget` widget_uuid=<...>

**Expected end state**:
- Widget gone from the dashboard.

**Verify by**:
- `manage_dashboard` operation=read → Charts tab has no widgets.

**Watch for**:
- LLM passing `widget_id` (the type identifier) instead of `widget_uuid` (the instance identifier) — only works if exactly one instance exists; otherwise should pick uuid.
- LLM passing the widget **title** ("the bar chart") as an identifier — must be rejected.

---

## Coverage map

| Tool | Covered by scenario |
|------|---------------------|
| `get_workspace_snapshot` | 1, 5, 6, 11, 12 |
| `manage_dashboard` (create/read) | 1, 5, 6, 13 |
| `manage_navigation_bar` (typed tabs) | 2 |
| `navigate_workspace` (tab) | 3, 4 |
| `add_generative_widget` (note) | 3 |
| `add_generative_widget` (chart, **camelCase chart_params**) | 4 |
| `update_widget_layout` | 6 |
| `list_available_widgets` | 7, 8 |
| `get_widget_schema` | 7, 8 |
| `get_params_options` | 7 (conditional) |
| `create_widget` | 8 |
| `read_widget` | 3, 8 |
| `manage_backends` (typed endpoint_headers) | 9 |
| `manage_apps` | 10 |
| `assign_tasks_to_agents` (typed task_requests) | 11 |
| `get_widget_data` | 12 |
| `delete_widget` | 13 |
| `update_widget` (config-only) | not covered — add a scenario when a widget has a non-trivial UI args contract |
| `get_skill_content` | not covered — add when there's a deterministic skill to fetch |
| `manage_dashboard` operation=update | not covered — add a "rename this dashboard to X" scenario |

## Round 1 migration regression nets

Five wire-shape contracts you specifically don't want silently breaking. Each scenario above has a "Watch for" callout for the relevant one.

| Wire field | Scenario | Failure mode to spot |
|------------|----------|---------------------|
| `tabs: [{name}]` | 2 | string array, `tab_id` extras, blank name |
| `chart_params` camelCase | 4 | snake_case keys on the bridge → silent chart failure |
| `endpoint_headers: [{key,value,location}]` | 9 | stringified, missing `location` default, camelCased keys |
| `task_requests: [{id, description, assigned_holder_url, assigned_agent_id}]` | 11 | camelCased field names |
| `rename_map: {old: new}` | (add a "rename a tab" scenario) | not yet covered — add scenario 14 |

## Future work

- **Scenario 14**: rename a tab (`manage_navigation_bar` operation=rename_tabs, typed `rename_map`). Easy add once a tab exists.
- **Test backend** at `tests/fixtures/sample_backend/` — small FastAPI app that ships `widgets.json` + `apps.json` + 2–3 endpoints. Makes scenarios 7–10 deterministic and reproducible without depending on an external backend.
- **Pytest mirror** at `tests/test_smoke_scenarios.py` — same scenarios driven via direct `server.call_tool` (no LLM). Catches contract drift in CI on every push.
- **Automated runner** at `scripts/smoke.py` — drives Claude API with the MCP attached, asserts on dashboard end-state. Manual / on-demand, not CI.
