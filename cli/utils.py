import questionary
from typing import List, Optional, Tuple, Dict

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout as PTLayout
from prompt_toolkit.layout.containers import Window as PTWindow
from prompt_toolkit.layout.controls import FormattedTextControl as PTFormattedTextControl
from rich.console import Console

from cli.models import AnalystType
from tradingagents.llm_clients.model_catalog import get_model_options
from tradingagents.runtime.options import (
    ANALYST_OPTIONS,
    ANTHROPIC_EFFORT_OPTIONS,
    GOOGLE_THINKING_LEVEL_OPTIONS,
    OPENAI_REASONING_EFFORT_OPTIONS,
    OUTPUT_LANGUAGE_OPTIONS,
    PROVIDER_OPTIONS,
    RESEARCH_DEPTH_OPTIONS,
    TICKER_INPUT_EXAMPLES,
)
from tradingagents.runtime.validation import (
    RunRequestValidationError,
    normalize_analysis_date,
    normalize_ticker_symbol as runtime_normalize_ticker_symbol,
)

console = Console()

ANALYST_ORDER = [
    (option.label, AnalystType(option.value.value))
    for option in ANALYST_OPTIONS
]


def get_ticker() -> str:
    """Prompt the user to enter a ticker symbol."""
    ticker = questionary.text(
        f"Enter the exact ticker symbol to analyze ({TICKER_INPUT_EXAMPLES}):",
        validate=lambda x: len(x.strip()) > 0 or "Please enter a valid ticker symbol.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not ticker:
        console.print("\n[red]No ticker symbol provided. Exiting...[/red]")
        exit(1)

    return normalize_ticker_symbol(ticker)


def normalize_ticker_symbol(ticker: str) -> str:
    """Normalize ticker input while preserving exchange suffixes."""
    return runtime_normalize_ticker_symbol(ticker)


def get_analysis_date() -> str:
    """Prompt the user to enter a date in YYYY-MM-DD format."""
    def validate_date(date_str: str) -> bool:
        try:
            normalize_analysis_date(date_str)
            return True
        except RunRequestValidationError:
            return False

    date = questionary.text(
        "Enter the analysis date (YYYY-MM-DD):",
        validate=lambda x: validate_date(x.strip())
        or "Please enter a valid date in YYYY-MM-DD format.",
        style=questionary.Style(
            [
                ("text", "fg:green"),
                ("highlighted", "noinherit"),
            ]
        ),
    ).ask()

    if not date:
        console.print("\n[red]No date provided. Exiting...[/red]")
        exit(1)

    return date.strip()


def select_analysts() -> List[AnalystType]:
    """Select analysts using an interactive multi-select prompt."""
    choices = _prompt_analyst_selection()

    if not choices:
        console.print("\n[red]No analysts selected. Exiting...[/red]")
        exit(1)

    return choices


def _prompt_analyst_selection() -> List[AnalystType]:
    app = _build_analyst_selection_app()
    return app.run()


def _build_analyst_selection_app() -> Application:
    selected_indices: set[int] = set()
    cursor_index = 0
    error_message = ""

    style = questionary.Style(
        [
            ("question", "fg:green bold"),
            ("instruction", "fg:#888888"),
            ("pointer", "fg:green bold"),
            ("selected-marker", "fg:green bold"),
            ("unselected-marker", "fg:#888888"),
            ("text", ""),
            ("error", "fg:red bold"),
        ]
    )

    def is_all_selected() -> bool:
        return len(selected_indices) == len(ANALYST_ORDER)

    def toggle_current() -> None:
        nonlocal error_message
        error_message = ""
        if cursor_index in selected_indices:
            selected_indices.remove(cursor_index)
        else:
            selected_indices.add(cursor_index)

    def toggle_all() -> None:
        nonlocal error_message
        error_message = ""
        if is_all_selected():
            selected_indices.clear()
        else:
            selected_indices.clear()
            selected_indices.update(range(len(ANALYST_ORDER)))

    def get_prompt_text():
        fragments = [
            ("class:question", "Select Your [Analysts Team]:\n"),
            (
                "class:instruction",
                "- Press Space to select/unselect analysts\n"
                "- Press 'a' to select/unselect all\n"
                "- Press Enter when done\n\n",
            ),
        ]

        for index, (label, _value) in enumerate(ANALYST_ORDER):
            pointer = "›" if index == cursor_index else " "
            marker = "●" if index in selected_indices else "○"
            marker_style = (
                "class:selected-marker"
                if index in selected_indices
                else "class:unselected-marker"
            )
            pointer_style = "class:pointer" if index == cursor_index else "class:text"
            fragments.append((pointer_style, f"{pointer} "))
            fragments.append((marker_style, f"{marker} "))
            fragments.append(("class:text", f"{label}\n"))

        if error_message:
            fragments.append(("class:error", f"\n{error_message}"))

        return fragments

    kb = KeyBindings()

    @kb.add(Keys.Up, eager=True)
    @kb.add("k", eager=True)
    def _move_up(_event) -> None:
        nonlocal cursor_index
        cursor_index = (cursor_index - 1) % len(ANALYST_ORDER)

    @kb.add(Keys.Down, eager=True)
    @kb.add("j", eager=True)
    def _move_down(_event) -> None:
        nonlocal cursor_index
        cursor_index = (cursor_index + 1) % len(ANALYST_ORDER)

    @kb.add(" ", eager=True)
    def _toggle(_event) -> None:
        toggle_current()

    @kb.add("a", eager=True)
    @kb.add("A", eager=True)
    @kb.add(Keys.ControlA, eager=True)
    def _toggle_all(_event) -> None:
        toggle_all()

    @kb.add(Keys.ControlC, eager=True)
    @kb.add(Keys.ControlQ, eager=True)
    def _abort(event) -> None:
        event.app.exit(exception=KeyboardInterrupt)

    @kb.add(Keys.Enter, eager=True)
    @kb.add(Keys.ControlM, eager=True)
    def _submit(event) -> None:
        nonlocal error_message
        if not selected_indices:
            error_message = "You must select at least one analyst."
            return
        event.app.exit(
            result=[ANALYST_ORDER[index][1] for index in sorted(selected_indices)]
        )

    control = PTFormattedTextControl(get_prompt_text, focusable=True)
    return Application(
        layout=PTLayout(PTWindow(content=control, always_hide_cursor=True)),
        key_bindings=kb,
        style=style,
        full_screen=False,
    )


def select_research_depth() -> int:
    """Select research depth using an interactive selection."""

    choice = questionary.select(
        "Select Your [Research Depth]:",
        choices=[
            questionary.Choice(option.label, value=option.value)
            for option in RESEARCH_DEPTH_OPTIONS
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:yellow noinherit"),
                ("highlighted", "fg:yellow noinherit"),
                ("pointer", "fg:yellow noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print("\n[red]No research depth selected. Exiting...[/red]")
        exit(1)

    return choice


def select_shallow_thinking_agent(provider) -> str:
    """Select shallow thinking llm engine using an interactive selection."""

    choice = questionary.select(
        "Select Your [Quick-Thinking LLM Engine]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in get_model_options(provider, "quick")
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print(
            "\n[red]No shallow thinking llm engine selected. Exiting...[/red]"
        )
        exit(1)

    return choice


def select_deep_thinking_agent(provider) -> str:
    """Select deep thinking llm engine using an interactive selection."""

    choice = questionary.select(
        "Select Your [Deep-Thinking LLM Engine]:",
        choices=[
            questionary.Choice(display, value=value)
            for display, value in get_model_options(provider, "deep")
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()

    if choice is None:
        console.print("\n[red]No deep thinking llm engine selected. Exiting...[/red]")
        exit(1)

    return choice

def select_llm_provider() -> tuple[str, str]:
    """Select the OpenAI api url using interactive selection."""

    choice = questionary.select(
        "Select your LLM Provider:",
        choices=[
            questionary.Choice(
                option.label,
                value=(option.label, option.backend_url),
            )
            for option in PROVIDER_OPTIONS
        ],
        instruction="\n- Use arrow keys to navigate\n- Press Enter to select",
        style=questionary.Style(
            [
                ("selected", "fg:magenta noinherit"),
                ("highlighted", "fg:magenta noinherit"),
                ("pointer", "fg:magenta noinherit"),
            ]
        ),
    ).ask()
    
    if choice is None:
        console.print("\n[red]no OpenAI backend selected. Exiting...[/red]")
        exit(1)
    
    display_name, url = choice
    print(f"You selected: {display_name}\tURL: {url}")

    return display_name, url


def ask_openai_reasoning_effort() -> str:
    """Ask for OpenAI reasoning effort level."""
    return questionary.select(
        "Select Reasoning Effort:",
        choices=[
            questionary.Choice(option.label, option.value)
            for option in OPENAI_REASONING_EFFORT_OPTIONS
        ],
        style=questionary.Style([
            ("selected", "fg:cyan noinherit"),
            ("highlighted", "fg:cyan noinherit"),
            ("pointer", "fg:cyan noinherit"),
        ]),
    ).ask()


def ask_anthropic_effort() -> str | None:
    """Ask for Anthropic effort level.

    Controls token usage and response thoroughness on Claude 4.5+ and 4.6 models.
    """
    return questionary.select(
        "Select Effort Level:",
        choices=[
            questionary.Choice(option.label, option.value)
            for option in ANTHROPIC_EFFORT_OPTIONS
        ],
        style=questionary.Style([
            ("selected", "fg:cyan noinherit"),
            ("highlighted", "fg:cyan noinherit"),
            ("pointer", "fg:cyan noinherit"),
        ]),
    ).ask()


def ask_gemini_thinking_config() -> str | None:
    """Ask for Gemini thinking configuration.

    Returns thinking_level: "high" or "minimal".
    Client maps to appropriate API param based on model series.
    """
    return questionary.select(
        "Select Thinking Mode:",
        choices=[
            questionary.Choice(option.label, option.value)
            for option in GOOGLE_THINKING_LEVEL_OPTIONS
        ],
        style=questionary.Style([
            ("selected", "fg:green noinherit"),
            ("highlighted", "fg:green noinherit"),
            ("pointer", "fg:green noinherit"),
        ]),
    ).ask()


def ask_output_language() -> str:
    """Ask for report output language."""
    choice = questionary.select(
        "Select Output Language:",
        choices=[
            questionary.Choice(option.label, option.value)
            for option in OUTPUT_LANGUAGE_OPTIONS
        ],
        style=questionary.Style([
            ("selected", "fg:yellow noinherit"),
            ("highlighted", "fg:yellow noinherit"),
            ("pointer", "fg:yellow noinherit"),
        ]),
    ).ask()

    if choice == "custom":
        return questionary.text(
            "Enter language name (e.g. Turkish, Vietnamese, Thai, Indonesian):",
            validate=lambda x: len(x.strip()) > 0 or "Please enter a language name.",
        ).ask().strip()

    return choice
