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

## Additional Bug Fixes Landed During Implementation

These were discovered while validating the refactor work and were fixed as part of the implementation checkpoint.

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

- `tests/test_runtime_contracts.py`
- `tests/test_runtime_validation.py`
- `tests/test_runtime_session_state.py`
- `tests/test_cli_prompt_shortcuts.py`

Expanded:

- `tests/test_google_api_key.py`
- `tests/test_ticker_symbol_handling.py`

Current checkpoint:

- Full test suite passes after the latest fixes.

## Current Status Against The Plan

Completed:

- Phase 0
- Phase 1
- Phase 2

Next planned work:

- Phase 3. Extract Shared Run Orchestration

## Notes For The Next Stage

- `cli/main.py` still owns the top-level run orchestration, log-file decoration, result-directory creation, final save/display prompts, and graph startup sequence.
- The next step should extract that orchestration into a reusable runtime runner so both CLI and Web can start runs through the same execution path.
- The CLI now has some custom analyst-picker UI logic that is intentionally presentation-layer-specific and should remain in `cli/`, while validation and execution continue moving into `tradingagents/runtime/`.
