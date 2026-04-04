# AGENTS.md

This file gives coding agents project-specific guidance for working in this repository.

## Project Overview

- `TradingAgents` is a Python trading-research framework built around multiple LLM-powered agents.
- The main package lives in `tradingagents/`.
- The interactive CLI lives in `cli/` and is exposed as the `tradingagents` console script.
- `main.py` is a simple example entry point for running the graph directly.
- Tests live in `tests/` and currently use the standard library `unittest` style.
- The biggest upcoming milestone is building a Web UI for the project.
- The Web UI roadmap and task breakdown live in `docs/web-ui-implementation-plan.md`; consult it when working on planning, architecture, or implementation related to the Web UI.

## Important Constraints

- Treat the project as research software, not a source of trading or investment advice.
- Many runtime paths depend on external APIs and environment variables. Avoid introducing tests that require live network access or real credentials.
- Prefer deterministic unit tests with mocks, fixtures, or pure functions over end-to-end runs against providers.
- Do not commit secrets, API keys, or filled-in `.env` files.

## Repository Map

- `tradingagents/agents/`: agent role implementations and shared agent utilities
- `tradingagents/graph/`: graph construction and orchestration
- `tradingagents/llm_clients/`: provider-specific model clients, validation, and factory logic
- `tradingagents/runtime/`: runtime validation, schemas, and session/state helpers
- `tradingagents/dataflows/`: market/news/fundamental data providers
- `cli/`: Typer CLI, prompts, display, and announcements
- `tests/`: unit tests for CLI/runtime/model behavior
- `docs/`: planning and implementation notes for the web UI work

## Working Style

- Make focused, minimal changes that match the existing code style.
- Preserve public APIs unless the task explicitly requires a breaking change.
- Avoid broad refactors unless they are necessary for the requested fix.
- Break larger tasks into clear stages and validate each stage before moving on.
- When changing behavior, update or add tests in the nearest relevant test file when practical.
- If a change touches provider/model selection, check whether `tradingagents/llm_clients/model_catalog.py`, validators, and tests also need updates.
- If a change touches CLI prompts or validation, check for corresponding coverage in `tests/test_cli_prompt_shortcuts.py`, `tests/test_runtime_validation.py`, and `tests/test_runtime_contracts.py`.

## Stage Gate Requirement

- After each meaningful stage of work, write or update the relevant tests.
- After each stage, run the relevant tests before continuing.
- Do not assume a stage is complete just because the code looks correct; use test results to verify it.
- After reporting the result of a completed stage, explicitly ask the user for feedback or confirmation before moving to the next major stage.
- Treat user feedback as a required checkpoint, especially for behavior changes, UI/CLI changes, and refactors.

## Setup And Common Commands

Use the repository root as the working directory.

Install dependencies:

```bash
python -m pip install -e .
```

Run the CLI from source:

```bash
python -m cli.main
```

Run the example script:

```bash
python main.py
```

Run the full test suite:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Run a focused test module:

```bash
python -m unittest tests.test_runtime_validation
```

## Environment Notes

- Copy `.env.example` when local credentials are needed.
- Common variables include `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY`, `OPENROUTER_API_KEY`, and optionally `ALPHA_VANTAGE_API_KEY`.
- Prefer code paths that work without optional credentials when writing tests or examples.

## Editing Guidance

- Keep changes ASCII unless the target file already uses non-ASCII text.
- Follow the existing structure and naming conventions in each module.
- Avoid adding new dependencies unless they are clearly justified.
- Do not reformat unrelated code just to satisfy personal style preferences.
- Add brief comments only where the logic is genuinely non-obvious.

## Validation Expectations

- For small changes, run the most relevant targeted tests.
- For cross-cutting changes, run the full `unittest` suite.
- Testing is required after each stage, not only at the end of the task.
- When new behavior is added, prefer adding the test first or alongside the code change.
- If you cannot run validation because of missing credentials, network limits, or environment issues, say so clearly in your summary.

## Safe Defaults For Agents

- Prefer mocked or local-only validation over live API calls.
- Prefer fixing root causes over adding special cases.
- Keep user-facing CLI output readable and consistent with the existing Rich/Typer patterns.
- When unsure, choose the least risky implementation that preserves current behavior.
- Pause after each validated stage and request user feedback to make sure everything works as expected.
