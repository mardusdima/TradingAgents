# TradingAgents Web UI Implementation Progress

## Purpose

This document records the implementation progress completed so far for the Web UI plan, including the runtime refactors already landed, the issues encountered during implementation, and the fixes that were applied.

Related plan:

- [Web UI Implementation Plan](/Users/dmytro_mardus/PycharmProjects/TradingAgents/docs/web-ui-implementation-plan.md)

## Completed So Far

### Phase 0. Shared Contracts

Completed:

- Added shared runtime option metadata in `tradingagents/runtime/options.py`.
- Added shared runtime schemas in `tradingagents/runtime/schemas.py`.
- Moved provider definitions, analyst options, research depth options, language options, and runtime defaults out of CLI-local constants.
- Updated CLI option prompts and default config to consume shared runtime metadata.

Key outcome:

- CLI and future Web code now read from the same source of truth for selectable runtime inputs and default values.

### Phase 1. Shared Validation And Normalization

Completed:

- Added shared request validation in `tradingagents/runtime/validation.py`.
- Moved ticker normalization into runtime validation.
- Moved analysis date validation into runtime validation.
- Added provider validation and strict-model validation for supported providers.
- Added provider-specific field validation for Google/OpenAI/Anthropic thinking or effort fields.
- Added analyst-selection, research-depth, and output-language validation.
- Updated CLI input flow and run startup to validate through the shared runtime request object before graph execution.

Key outcome:

- Invalid requests now fail before graph execution starts.
- CLI and future Web entry points can share the exact same input rules.

### Phase 2. Shared Session State And Chunk Processing

Completed:

- Added shared runtime stats callback in `tradingagents/runtime/stats.py`.
- Added shared runtime session state in `tradingagents/runtime/session_state.py`.
- Moved message classification and tool-call extraction into shared runtime helpers.
- Moved analyst/research/trader/risk/portfolio status progression into shared chunk processing.
- Added structured report accumulation for:
  - analyst reports
  - bull researcher content
  - bear researcher content
  - research manager decision
  - trader plan
  - aggressive risk content
  - conservative risk content
  - neutral risk content
  - portfolio decision
- Added stable event history capture in the session snapshot model.
- Refactored the CLI to render from the shared runtime session state instead of the old CLI-owned `MessageBuffer`.

Key outcome:

- Stream chunks can now be processed without Rich or browser dependencies.
- CLI and future Web rendering can share the same state/event shape.

### Phase 3. Shared Run Orchestration

Completed:

- Added shared runtime report/export helpers in `tradingagents/runtime/reporting.py`.
- Added reusable runtime runner orchestration in `tradingagents/runtime/runner.py`.
- Moved graph configuration setup, result-directory creation, section report persistence, and `message_tool.log` writing into the shared runner.
- Added runtime runner hooks for snapshot updates, message appends, tool calls, run completion, and failure handling.
- Centralized final-state handling, processed trade decision extraction, and normalized runtime error propagation.
- Updated the CLI to execute analyses through the shared runner while preserving the existing Rich live display and post-run save/display prompts.

Key outcome:

- A single runtime component can now execute the end-to-end analysis flow without depending on CLI rendering code.
- The CLI now uses the shared execution path that the Web backend can build on next.

### Phase 4. Refactor CLI To Use Shared Runtime

Completed:

- Refactored the CLI live layout rendering to consume `SessionSnapshot` data directly instead of reading from a shared mutable session-state instance.
- Added snapshot-driven rendering helpers in `cli/rendering.py` for:
  - team-grouped agent status rows
  - merged message/tool activity feed rows
  - completed report counts
- Removed the CLI's dependency on injecting its own `RuntimeSessionState` into the runtime runner.
- Preserved the existing Rich live dashboard layout and post-run prompts while making the CLI a thinner presentation layer over shared runtime contracts.
- Added an error-state analysis panel path so failed runs can still render a snapshot-driven UI state.

Key outcome:

- The CLI now renders from the same shared snapshot contract that the Web UI will consume, reducing CLI-specific state ownership further.
- Remaining CLI responsibilities are primarily presentation and user prompts.

### Phase 5. Build Web Backend

Completed:

- Added a FastAPI web application in `tradingagents/web/app.py`.
- Added a lightweight in-memory run registry and shared-runtime-backed web service in `tradingagents/web/api.py`.
- Enforced the v1 single-active-run guard for the web flow.
- Implemented:
  - `GET /api/options`
  - `POST /api/runs`
  - `GET /api/runs/{id}`
  - `GET /api/runs/{id}/events`
  - `POST /api/runs/{id}/export`
  - `GET /health`
  - `GET /`
- Added JSON serialization helpers for shared runtime option metadata and session snapshots.
- Reused the shared runtime runner and shared export logic for web-triggered analyses and exports.
- Added a minimal static HTML/CSS/JS shell so the backend can be opened in a browser during development.

Key outcome:

- The project now has a functioning Web backend that can validate requests, start a run in the background, expose live snapshot events over SSE, return current state, and export reports without duplicating graph orchestration logic.
- The backend contract needed for the dashboard UI is now available.

### Phase 6. Build Web Dashboard UI

Completed:

- Replaced the placeholder web shell with a three-column dashboard in `tradingagents/web/templates/index.html`.
- Added a browser-side dashboard controller in `tradingagents/web/static/app.js` that:
  - loads runtime option metadata from `/api/options`
  - populates the setup form
  - handles provider/model conditional behavior
  - validates form input before submission
  - starts runs through `POST /api/runs`
  - subscribes to `/api/runs/{id}/events` over SSE
  - renders agent status, events, tool calls, report output, final decision, and footer stats from shared snapshots
  - supports reset and export actions
- Added desktop-first responsive styling in `tradingagents/web/static/styles.css`.
- Preserved the single-page, server-rendered HTML/CSS/JS approach with no separate frontend toolchain.

Key outcome:

- A user can now drive the core workflow from the browser with a real dashboard layout and live shared-runtime-backed updates.
- The browser client now consumes the same snapshot contract as the CLI.

## Additional Bug Fixes Landed During Implementation

These were discovered while validating the refactor work and were fixed as part of the implementation checkpoint.

### Web Dashboard Run Restore, Stop Flow, And Layout Refinements

Issue:

- The first browser dashboard cut exposed several real-world usability problems during manual validation:
  - the initial empty state locked the form because it looked like an active run
  - refreshing the page lost the visible session while the backend still enforced the single-active-run guard
  - stop requests showed success feedback but did not explain the delay before cancellation completed
  - active-run configuration values were not restored into the setup form on refresh
  - the desktop layout overused vertical space and needed multiple passes to improve density and panel readability

Fix:

- Added browser-side idle handling so the setup form remains editable when no run exists.
- Added active-run restore support through:
  - `GET /api/runs/active`
  - browser-side persisted `runId`
  - reconnect logic on page load and on `409` active-run conflicts
- Added cooperative stop support across the shared runtime and web service, including:
  - runtime cancellation hooks and terminal canceled snapshots
  - `POST /api/runs/{id}/stop`
  - immediate `stopping` UI feedback while the current LLM/tool step finishes
  - clearer stop-state copy explaining that cancellation waits for the active call to yield control
- Restored active run inputs back into the Analysis Configuration panel from snapshot `selected_inputs` after refresh.
- Refined the desktop dashboard layout to use horizontal space more effectively, including:
  - a more compact header
  - a denser setup panel
  - tabbed report viewing for the results area
  - moving the stats strip to the upper portion of the page
  - restoring page-level vertical scrolling after fixed-height panel constraints proved too fragile in practice

Key outcome:

- The browser dashboard now reconnects reliably to active runs, supports cooperative stop/cancel behavior more transparently, restores run inputs after refresh, and uses a more practical desktop layout without the earlier overlap and lock-state confusion.

### Google `base_url` Forwarding Bug

Issue:

- Google runs started failing because `base_url` was being forwarded into `ChatGoogleGenerativeAI`, which does not accept it.

Fix:

- Removed `base_url` forwarding from `tradingagents/llm_clients/google_client.py`.

### Corrupted Ticker / Filesystem Path Bug

Issue:

- A malformed ticker value with invalid characters passed validation and later caused `mkdir` failures when used in the results path.

Fix:

- Tightened ticker validation in `tradingagents/runtime/validation.py` to reject invalid or unsupported ticker characters before execution starts.

### Analyst Multi-Select `a` Shortcut Regression

Issue:

- The original Questionary checkbox prompt stopped reliably handling the `a` toggle-all shortcut in the current environment.

Fix:

- Replaced the analyst picker with a small custom prompt-toolkit multi-select implementation in `cli/utils.py`.
- Preserved `Space`, `a`, `A`, `Ctrl-A`, arrow keys, and `j`/`k`.
- Adjusted rendering so only the selection marker changes state, not the full label row.

### Rich `Layout` Namespace Collision

Issue:

- The custom analyst picker originally imported prompt-toolkit `Layout` into `cli/utils.py`.
- Because `cli/main.py` uses `from cli.utils import *`, that shadowed Rich's `Layout` and caused CLI layout initialization to fail.

Fix:

- Aliased prompt-toolkit layout imports in `cli/utils.py` so they do not leak into the CLI namespace.

## Tests Added Or Expanded

Added:

- `tests/test_cli_rendering.py`
- `tests/test_runtime_contracts.py`
- `tests/test_runtime_reporting.py`
- `tests/test_runtime_runner.py`
- `tests/test_runtime_validation.py`
- `tests/test_runtime_session_state.py`
- `tests/test_cli_prompt_shortcuts.py`
- `tests/test_web_api.py`

Expanded:

- `tests/test_google_api_key.py`
- `tests/test_ticker_symbol_handling.py`

Current checkpoint:

- Full test suite passes after the dashboard UI implementation checkpoint and subsequent browser validation fixes.

## Current Status Against The Plan

Completed:

- Phase 0
- Phase 1
- Phase 2
- Phase 3
- Phase 4
- Phase 5
- Phase 6

Next planned work:

- Phase 7. Report Export And Persistence Alignment

## Notes For The Next Stage

- The browser dashboard is now wired to the backend contract and can start runs, render snapshot updates, and request exports.
- The browser dashboard has also gone through a post-Phase-6 stabilization pass covering reconnect behavior, cooperative stop UX, restored setup-form state, and desktop layout refinement.
- The next step should tighten export/persistence behavior so Web outputs align deliberately with the shared runtime artifact structure and failed/partial runs are handled cleanly.
- Browser-level automation has not been added yet because no Playwright MCP server is available in this session; current validation relies on backend tests and local script/server checks.
