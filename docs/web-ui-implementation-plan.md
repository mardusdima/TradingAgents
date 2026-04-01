# TradingAgents Web UI Implementation Plan

## Goal

Add a simple dashboard-style Web UI with feature parity to the existing CLI while minimizing code changes and keeping the current trading workflow logic in the shared Python core.

## Guiding Principles

- Reuse `TradingAgentsGraph` and existing graph streaming behavior.
- Avoid duplicating business logic between CLI and Web.
- Preserve all current CLI inputs, provider-specific settings, live progress, report output, and export behavior.
- Keep v1 local, single-user, and effectively single-active-run to avoid concurrency issues with process-global config.
- Prefer Python-only implementation for v1 to avoid introducing a separate frontend toolchain unless it becomes necessary.

## Scope For V1

- One desktop-first dashboard page
- Local/server-hosted Web UI
- Same input surface as CLI
- Live run progress, messages, tool calls, report updates, and stats
- Final compiled report view and export action
- No auth
- No multi-user collaboration
- No run history page

## Proposed Target Architecture

### Shared Runtime Layer

Create a new shared runtime layer that both CLI and Web can use.

Suggested module layout:

- `tradingagents/runtime/options.py`
- `tradingagents/runtime/schemas.py`
- `tradingagents/runtime/stats.py`
- `tradingagents/runtime/session_state.py`
- `tradingagents/runtime/runner.py`
- `tradingagents/runtime/reporting.py`

Responsibilities:

- input defaults and dropdown options
- input normalization and validation
- run request schema
- session state and event snapshot shaping
- graph execution and chunk processing
- stats tracking
- report compilation and export
- disk logging

### CLI Layer

Keep `cli/` as a presentation layer:

- prompt for inputs
- display Rich UI
- call shared runtime runner
- render snapshots from shared session state

### Web Layer

Add a lightweight web module:

- `tradingagents/web/app.py`
- `tradingagents/web/api.py`
- `tradingagents/web/templates/index.html`
- `tradingagents/web/static/styles.css`
- `tradingagents/web/static/app.js`

Recommended stack for v1:

- FastAPI backend
- SSE for live updates
- server-served HTML/CSS/JS
- vanilla JS or very light browser code only

## Known Constraints To Design Around

### Process-global config

`tradingagents.dataflows.config` uses a module-level config object, so v1 should support only one active run at a time unless that global behavior is refactored.

### CLI state logic is mixed with rendering

Current run orchestration, chunk parsing, status transitions, report aggregation, and Rich rendering are all mixed in `cli/main.py`. This should be separated before or while adding Web support.

### Live report aggregation is currently lossy

The CLI updates some sections by overwriting the same keys during the run. Web should use structured section storage so intermediate debate/risk content and final decisions can be represented cleanly.

## Detailed Subtasks

### Phase 0. Define Shared Contracts

1. Create a single source of truth for all selectable inputs.
2. Move provider definitions, backend URLs, analyst options, research depth options, and output language options out of `cli/utils.py` into a shared runtime module.
3. Define request/response schemas for a run.
4. Define a normalized session snapshot schema for:
   - selected inputs
   - run status
   - agent statuses
   - messages
   - tool calls
   - current report
   - compiled report
   - stats
   - export info
   - errors
5. Define shared enums or constants for:
   - provider names
   - analyst keys
   - agent names
   - report section keys
   - event types
   - run lifecycle states

Acceptance:

- CLI and Web can both read the same metadata for dropdowns and defaults.
- No UI-specific values remain hardcoded in more than one place.

### Phase 1. Extract Shared Input Validation And Normalization

1. Move ticker normalization into shared runtime validation.
2. Move analysis date validation into shared runtime validation.
3. Preserve the current non-empty ticker and no-future-date behavior.
4. Add provider-specific validation rules:
   - provider is supported
   - model exists for strict providers when chosen from predefined lists
   - provider-specific thinking/effort field is only accepted for the matching provider
5. Add validation for:
   - at least one analyst selected
   - research depth is one of supported values
   - output language is present
6. Support custom language input while keeping prefills for the standard list.

Acceptance:

- CLI and Web both use the same validation rules.
- Invalid requests fail before graph execution starts.

### Phase 2. Extract Shared Session State And Chunk Processing

1. Move `StatsCallbackHandler` into shared runtime.
2. Replace or extract `MessageBuffer` into a reusable session state model.
3. Preserve the current team/agent mapping logic.
4. Move status transition logic out of the CLI file:
   - analyst progression
   - research team progression
   - trader progression
   - risk team progression
   - portfolio manager completion
5. Move message classification and tool-call extraction into shared helpers.
6. Introduce structured report accumulation:
   - analyst reports
   - bull researcher content
   - bear researcher content
   - research manager decision
   - trader plan
   - aggressive/conservative/neutral risk content
   - portfolio decision
7. Keep support for:
   - current report display
   - compiled report display
   - completed report counts
   - elapsed time
8. Keep a stable event history format so both CLI and Web can render it differently without changing backend logic.

Acceptance:

- Shared session state can be updated from stream chunks without Rich or browser dependencies.
- CLI rendering can read from it without losing current behavior.

### Phase 3. Extract Shared Run Orchestration

1. Create a reusable runner that accepts a validated run request.
2. Move graph configuration setup into the runner:
   - selected analysts
   - research depth
   - provider/model settings
   - output language
3. Move result directory creation and file logging into the runner.
4. Move graph streaming loop into the runner.
5. Expose runner hooks or event callbacks for:
   - snapshot updated
   - message appended
   - tool call appended
   - run completed
   - run failed
6. Ensure final state, processed decision, and export paths are available from the shared runner.
7. Keep current report writing behavior, but centralize it so Web export and CLI save share the same path.
8. Normalize all exceptions into user-safe run errors.

Acceptance:

- A single runtime component can execute the full analysis without any CLI rendering code.
- CLI and Web can both start a run through the same path.

### Phase 4. Refactor CLI To Use Shared Runtime

1. Update CLI prompts to read shared option metadata.
2. Keep the current questionary UX for input collection.
3. Replace direct graph-stream handling in `cli/main.py` with the shared runner.
4. Keep Rich layout rendering, but render from shared session snapshots instead of CLI-owned mutable logic.
5. Preserve existing CLI output features:
   - welcome flow
   - announcements
   - live progress
   - messages and tools
   - current report panel
   - footer stats
   - post-run save prompt
   - full report display
6. Confirm that CLI still writes reports and logs to the same expected folders unless intentionally changed.

Acceptance:

- CLI behavior stays functionally equivalent after the refactor.
- CLI becomes a thin client over shared runtime logic.

### Phase 5. Build Web Backend

1. Add a FastAPI application module.
2. Add a simple run registry for in-memory session storage.
3. Enforce one active run at a time for v1.
4. Implement `GET /api/options`:
   - providers
   - models by provider and mode
   - analysts
   - research depth options
   - output languages
   - default values
5. Implement `POST /api/runs`:
   - validate request
   - reject if another run is active
   - create session
   - start background execution
6. Implement `GET /api/runs/{id}`:
   - return current snapshot
7. Implement `GET /api/runs/{id}/events`:
   - stream SSE snapshots or events during execution
8. Implement `POST /api/runs/{id}/export`:
   - trigger report export or return existing exported path
9. Implement health and static index routes.
10. Add serialization helpers for markdown report content, timestamps, statuses, and stats payloads.

Acceptance:

- Web backend can start a run, stream live state, and return final results without duplicating graph logic.

### Phase 6. Build Web Dashboard UI

1. Create a single-page dashboard shell with three columns:
   - setup
   - activity
   - results
2. Build setup controls using prefilled data from `/api/options`.
3. Implement input widgets:
   - ticker text input
   - analysis date picker/input
   - output language dropdown
   - analyst multi-select
   - research depth dropdown
   - provider dropdown
   - quick-thinking model dropdown
   - deep-thinking model dropdown
   - conditional provider-specific field
4. Implement client-side conditional behavior:
   - update model dropdowns when provider changes
   - show/hide provider-specific effort field
   - preserve previously selected valid values where possible
5. Implement validation UX:
   - required ticker
   - invalid/future date
   - no analysts selected
   - unsupported provider/model combination
6. Implement running state UX:
   - disable or lock setup controls during active run
   - show ticker/date summary
   - show active/inactive action states
7. Implement activity column:
   - team-grouped agent status list
   - event feed
   - tool calls
   - error banner
8. Implement results column:
   - current report panel
   - compiled output panel
   - final decision emphasis
9. Implement footer stats bar:
   - agents completed / total
   - LLM calls
   - tool calls
   - token counts
   - reports completed / total
   - elapsed time
10. Implement post-run actions:
   - new analysis reset
   - export report

Acceptance:

- A user can run the full workflow from the browser with the same functional controls as the CLI.

### Phase 7. Report Export And Persistence Alignment

1. Reuse existing report save logic through shared runtime.
2. Ensure Web export produces the same or intentionally improved folder structure.
3. Decide whether Web auto-saves to `results/` during runs, manual export only, or both.
4. Keep `message_tool.log` generation if it remains useful for debugging.
5. Ensure compiled report generation is consistent between CLI and Web.
6. Ensure partial run artifacts are handled cleanly on error.

Acceptance:

- Exported outputs match the agreed structure and remain easy to inspect locally.

### Phase 8. Testing

1. Add unit tests for shared validation:
   - ticker normalization
   - date validation
   - analyst selection validation
   - provider-specific field validation
2. Add unit tests for shared options metadata.
3. Add unit tests for session-state transitions from mocked chunks.
4. Add unit tests for compiled report aggregation.
5. Add tests for report export structure.
6. Add API tests for:
   - options endpoint
   - run creation validation
   - single-active-run guard
   - snapshot retrieval
7. Add a minimal integration test that exercises the web runner with a mocked graph stream if practical.
8. Add a CLI regression test where possible for shared runner wiring.

Acceptance:

- New shared runtime behavior is covered by tests.
- Web-specific API contracts are covered by tests.

### Phase 9. Developer Experience And Packaging

1. Add a web entrypoint command or module run path.
2. Decide on command style:
   - `python -m tradingagents.web.app`
   - or a new script such as `tradingagents-web`
3. Update package discovery if new modules need explicit inclusion.
4. Add any missing web dependencies to project configuration.
5. Add local startup instructions for both CLI and Web.

Acceptance:

- A developer can start the web server from a clean checkout with documented commands.

### Phase 10. Documentation

1. Update `README.md` with Web UI usage.
2. Document feature parity and known v1 limitations.
3. Document the single-active-run limitation.
4. Document the shared runtime architecture so future work does not regress into duplicated CLI/Web logic.
5. Add screenshots or placeholders after implementation.

Acceptance:

- The repo clearly explains how to run and develop both interfaces.

## Suggested Implementation Order

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6
8. Phase 7
9. Phase 8
10. Phase 9
11. Phase 10

## Recommended Delivery Slices

### Slice 1. Shared runtime extraction with no Web yet

- phases 0 to 4
- result: CLI still works, architecture is ready for Web

### Slice 2. Minimal working Web backend plus read-only page shell

- phase 5 plus basic phase 6 shell
- result: browser can start runs and display live updates

### Slice 3. Full parity dashboard

- complete phase 6 and phase 7
- result: feature parity with CLI

### Slice 4. Hardening

- phases 8 to 10
- result: tested, documented, easier to maintain

## Risks And Mitigations

### Risk: duplicated logic between CLI and Web

Mitigation:

- force all run orchestration through shared runtime before building Web features deeply

### Risk: global config breaks concurrent runs

Mitigation:

- explicitly keep v1 to one active run
- document the limitation
- treat multi-run support as future work

### Risk: live state drift between CLI and Web

Mitigation:

- define one canonical session snapshot model
- make both UIs render from the same shape

### Risk: Web implementation grows into a frontend rewrite

Mitigation:

- keep v1 server-hosted and simple
- avoid JS framework/tooling unless needed after parity is reached

## Not In Scope For V1

- authentication
- multi-user sessions
- concurrent runs
- persistent run history page
- database-backed storage
- mobile-optimized UI
- major visual design system work

## Implementation Ready Exit Criteria

The task is complete when:

- CLI and Web both use the same runtime execution path
- Web exposes all current CLI inputs with prefilled supported options
- Web shows live progress, messages, tools, current report, compiled report, and stats
- export works from Web
- CLI behavior remains intact
- tests cover the new shared runtime and Web API surface
- docs explain how to run and maintain the feature
