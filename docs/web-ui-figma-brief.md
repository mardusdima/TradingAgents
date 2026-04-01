# TradingAgents Web UI Figma Brief

## Summary

Design the first browser UI as a **desktop-first single-page control center** that mirrors current CLI functionality without changing system behavior.

This v1 is:

- local and single-user
- exact CLI parity in browser form
- screen-first rather than design-system-first
- optimized for a clean long-term foundation

Grounding sources:

- `cli/main.py`
- `cli/utils.py`
- `tradingagents/default_config.py`
- `docs/architecture.md`

## Visual Direction

Create the UI as a **research workstation**, not a generic admin dashboard.

- Tone: focused, analytical, trustworthy, high-signal
- Layout feel: dense but readable, with clear operational hierarchy
- Base palette: warm off-white / soft graphite / muted slate
- Positive accents: emerald / teal for progress and completion
- Caution accents: amber for pending states
- Error accents: muted red for failures
- Surfaces: layered cards and report panels with subtle separation, not flat blocks
- Typography: editorial-meets-technical, with clear contrast between controls, logs, and narrative reports

## Figma Frame Set

Create one working file with these desktop frames:

### 1. `Control Center / Ready`

Primary frame for before a run starts.

Layout:

- Desktop frame: `1440 x 1200`
- Header across top
- Three-column content area
- Sticky footer stats bar optional in this state

Column structure:

- Left: `Setup`
- Center: `Run Activity`
- Right: `Results`

Left column content:

- Ticker input
- Analysis date input
- Output language selector
- Analyst multi-select control
- Research depth selector
- LLM provider selector
- Quick-thinking model selector
- Deep-thinking model selector
- Conditional provider-specific control:
  - OpenAI reasoning effort
  - Google thinking level
  - Anthropic effort
- Primary action button: `Run Analysis`

Center column content:

- Empty state explaining that live agent activity appears during execution
- Placeholder for agent progress table
- Placeholder for messages and tool calls

Right column content:

- Empty state for current report and final decision
- Compact explanation of what appears after execution

### 2. `Control Center / Running`

Same shell, but configured for active execution.

Behavior to visualize:

- Setup controls locked or visually de-emphasized during the run
- Current ticker/date summary visible near the top
- Center column becomes the operational focus

Center column sections:

- `Agent Progress`
  - grouped by team
  - status chips: pending / in progress / completed / error
- `Messages & Tools`
  - chronological event feed
  - distinguish agent text vs tool calls vs system events

Right column sections:

- `Current Report`
  - latest report section in progress
- `Compiled Output`
  - progressively assembled sections as they become available

Footer stats bar:

- Agents completed / total
- LLM calls
- Tool calls
- Tokens in / out
- Reports completed / total
- Elapsed time

### 3. `Control Center / Complete`

Completed analysis state with the same overall layout.

Left column:

- original selections still visible
- `New Analysis` secondary action
- `Export Report` primary or prominent secondary action

Center column:

- completed status overview
- final run summary
- optional collapsed event feed or most recent activity snapshot

Right column:

- Full compiled report with sections:
  - Analyst Team Reports
  - Research Team Decision
  - Trading Team Plan
  - Portfolio Management Decision

### 4. `Control Center / Validation + Error States`

Show focused states needed for implementation handoff.

Include:

- empty required ticker validation
- invalid or future date validation
- no analysts selected validation
- provider-specific field showing/hiding
- run failure banner or inline error state
- unavailable results empty state

## Minimal Component Set

Create only the components required to keep the first screens consistent.

### Core Shell

- Page header
- Section card
- Section header row
- Sticky footer stats bar

### Inputs

- Text input
- Date input
- Select / dropdown
- Multi-select checklist block
- Inline helper text
- Validation message

### Actions

- Primary button
- Secondary button
- Disabled button state

### Status + Activity

- Status chip
- Agent status row
- Team group header
- Event log row
- Tool call row
- Empty state block
- Error banner

### Report Rendering

- Report panel
- Report section header
- Markdown/narrative content container
- Final decision highlight card

## Layout Rules

- Keep the page inside a single control-center shell rather than a multi-step wizard
- Preserve visibility of setup, live progress, and results in one screen
- Make the center column the most operationally dense area
- Make the right column the most readable narrative area
- Ensure the right column can visually hold long markdown-style reports
- Avoid decorative charts in v1 unless they directly support existing CLI behavior

Suggested desktop proportions:

- Left setup column: `320px`
- Center activity column: `420px`
- Right results column: `min 520px`
- Content gap: `24px`
- Card padding: `20px` to `24px`

## CLI-to-UI Mapping

Mirror these current CLI inputs in the browser:

- ticker
- analysis date
- output language
- selected analysts
- research depth
- LLM provider
- quick-thinking model
- deep-thinking model
- provider-specific effort/thinking setting

Mirror these current CLI outputs in the browser:

- agent progress by team
- live messages
- live tool calls
- latest report section
- compiled final report
- token / tool / LLM counters
- elapsed time
- export/save result action

## Assumptions

- No authentication in v1
- No multi-user collaboration in v1
- No run history page in v1
- Desktop-first only for the initial Figma deliverable
- The web module reuses the existing Python graph rather than redefining workflow logic
