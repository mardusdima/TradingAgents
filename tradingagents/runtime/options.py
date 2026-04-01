from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS, get_model_options
from tradingagents.runtime.schemas import AnalystKey, ProviderName

TICKER_INPUT_EXAMPLES = "Examples: SPY, CNC.TO, 7203.T, 0700.HK"


@dataclass(frozen=True)
class ChoiceOption:
    label: str
    value: str


@dataclass(frozen=True)
class ProviderOption:
    label: str
    value: ProviderName
    backend_url: str


@dataclass(frozen=True)
class AnalystOption:
    label: str
    value: AnalystKey


@dataclass(frozen=True)
class ResearchDepthOption:
    label: str
    value: int


@dataclass(frozen=True)
class RuntimeDefaults:
    llm_provider: ProviderName
    backend_url: str
    quick_model: str
    deep_model: str
    research_depth: int
    output_language: str


@dataclass
class RuntimeOptionCatalog:
    defaults: RuntimeDefaults
    providers: List[ProviderOption] = field(default_factory=list)
    analysts: List[AnalystOption] = field(default_factory=list)
    research_depths: List[ResearchDepthOption] = field(default_factory=list)
    output_languages: List[ChoiceOption] = field(default_factory=list)
    google_thinking_levels: List[ChoiceOption] = field(default_factory=list)
    openai_reasoning_efforts: List[ChoiceOption] = field(default_factory=list)
    anthropic_efforts: List[ChoiceOption] = field(default_factory=list)
    models_by_provider: Dict[str, Dict[str, List[ChoiceOption]]] = field(
        default_factory=dict
    )


PROVIDER_OPTIONS = (
    ProviderOption(
        label="OpenAI",
        value=ProviderName.OPENAI,
        backend_url="https://api.openai.com/v1",
    ),
    ProviderOption(
        label="Google",
        value=ProviderName.GOOGLE,
        backend_url="https://generativelanguage.googleapis.com/v1",
    ),
    ProviderOption(
        label="Anthropic",
        value=ProviderName.ANTHROPIC,
        backend_url="https://api.anthropic.com/",
    ),
    ProviderOption(
        label="xAI",
        value=ProviderName.XAI,
        backend_url="https://api.x.ai/v1",
    ),
    ProviderOption(
        label="Openrouter",
        value=ProviderName.OPENROUTER,
        backend_url="https://openrouter.ai/api/v1",
    ),
    ProviderOption(
        label="Ollama",
        value=ProviderName.OLLAMA,
        backend_url="http://localhost:11434/v1",
    ),
)

ANALYST_OPTIONS = (
    AnalystOption(label="Market Analyst", value=AnalystKey.MARKET),
    AnalystOption(label="Social Media Analyst", value=AnalystKey.SOCIAL),
    AnalystOption(label="News Analyst", value=AnalystKey.NEWS),
    AnalystOption(label="Fundamentals Analyst", value=AnalystKey.FUNDAMENTALS),
)

RESEARCH_DEPTH_OPTIONS = (
    ResearchDepthOption(
        label="Shallow - Quick research, few debate and strategy discussion rounds",
        value=1,
    ),
    ResearchDepthOption(
        label="Medium - Middle ground, moderate debate rounds and strategy discussion",
        value=3,
    ),
    ResearchDepthOption(
        label="Deep - Comprehensive research, in depth debate and strategy discussion",
        value=5,
    ),
)

OUTPUT_LANGUAGE_OPTIONS = (
    ChoiceOption(label="English (default)", value="English"),
    ChoiceOption(label="Chinese (中文)", value="Chinese"),
    ChoiceOption(label="Japanese (日本語)", value="Japanese"),
    ChoiceOption(label="Korean (한국어)", value="Korean"),
    ChoiceOption(label="Hindi (हिन्दी)", value="Hindi"),
    ChoiceOption(label="Spanish (Español)", value="Spanish"),
    ChoiceOption(label="Portuguese (Português)", value="Portuguese"),
    ChoiceOption(label="French (Français)", value="French"),
    ChoiceOption(label="German (Deutsch)", value="German"),
    ChoiceOption(label="Arabic (العربية)", value="Arabic"),
    ChoiceOption(label="Russian (Русский)", value="Russian"),
    ChoiceOption(label="Custom language", value="custom"),
)

GOOGLE_THINKING_LEVEL_OPTIONS = (
    ChoiceOption(label="Enable Thinking (recommended)", value="high"),
    ChoiceOption(label="Minimal/Disable Thinking", value="minimal"),
)

OPENAI_REASONING_EFFORT_OPTIONS = (
    ChoiceOption(label="Medium (Default)", value="medium"),
    ChoiceOption(label="High (More thorough)", value="high"),
    ChoiceOption(label="Low (Faster)", value="low"),
)

ANTHROPIC_EFFORT_OPTIONS = (
    ChoiceOption(label="High (recommended)", value="high"),
    ChoiceOption(label="Medium (balanced)", value="medium"),
    ChoiceOption(label="Low (faster, cheaper)", value="low"),
)

DEFAULT_PROVIDER = ProviderName.OPENAI
DEFAULT_BACKEND_URL = next(
    provider.backend_url
    for provider in PROVIDER_OPTIONS
    if provider.value == DEFAULT_PROVIDER
)
DEFAULT_QUICK_MODEL = get_model_options(DEFAULT_PROVIDER.value, "quick")[0][1]
DEFAULT_DEEP_MODEL = get_model_options(DEFAULT_PROVIDER.value, "deep")[0][1]
DEFAULT_RESEARCH_DEPTH = RESEARCH_DEPTH_OPTIONS[0].value
DEFAULT_OUTPUT_LANGUAGE = OUTPUT_LANGUAGE_OPTIONS[0].value


def get_provider_option(provider: str | ProviderName) -> ProviderOption:
    provider_value = (
        provider
        if isinstance(provider, ProviderName)
        else ProviderName(str(provider).lower())
    )
    return next(option for option in PROVIDER_OPTIONS if option.value == provider_value)


def get_runtime_options_catalog() -> RuntimeOptionCatalog:
    models_by_provider = {
        provider: {
            mode: [
                ChoiceOption(label=label, value=value)
                for label, value in mode_options
            ]
            for mode, mode_options in provider_options.items()
        }
        for provider, provider_options in MODEL_OPTIONS.items()
    }

    return RuntimeOptionCatalog(
        providers=list(PROVIDER_OPTIONS),
        analysts=list(ANALYST_OPTIONS),
        research_depths=list(RESEARCH_DEPTH_OPTIONS),
        output_languages=list(OUTPUT_LANGUAGE_OPTIONS),
        google_thinking_levels=list(GOOGLE_THINKING_LEVEL_OPTIONS),
        openai_reasoning_efforts=list(OPENAI_REASONING_EFFORT_OPTIONS),
        anthropic_efforts=list(ANTHROPIC_EFFORT_OPTIONS),
        models_by_provider=models_by_provider,
        defaults=RuntimeDefaults(
            llm_provider=DEFAULT_PROVIDER,
            backend_url=DEFAULT_BACKEND_URL,
            quick_model=DEFAULT_QUICK_MODEL,
            deep_model=DEFAULT_DEEP_MODEL,
            research_depth=DEFAULT_RESEARCH_DEPTH,
            output_language=DEFAULT_OUTPUT_LANGUAGE,
        ),
    )
