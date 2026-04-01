from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable, List, Sequence

from tradingagents.llm_clients.validators import validate_model
from tradingagents.runtime.options import (
    DEFAULT_OUTPUT_LANGUAGE,
    RESEARCH_DEPTH_OPTIONS,
    get_provider_option,
)
from tradingagents.runtime.schemas import AnalystKey, ProviderName, RunRequest

SUPPORTED_RESEARCH_DEPTHS = {option.value for option in RESEARCH_DEPTH_OPTIONS}
GOOGLE_THINKING_LEVEL_FIELD = "google_thinking_level"
OPENAI_REASONING_EFFORT_FIELD = "openai_reasoning_effort"
ANTHROPIC_EFFORT_FIELD = "anthropic_effort"


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str


class RunRequestValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]):
        self.issues = list(issues)
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        return "; ".join(f"{issue.field}: {issue.message}" for issue in self.issues)


def normalize_ticker_symbol(ticker: object) -> str:
    normalized = str(ticker or "").strip().upper()
    if not normalized:
        raise RunRequestValidationError(
            [ValidationIssue("ticker", "Please enter a valid ticker symbol.")]
        )
    return normalized


def normalize_analysis_date(
    analysis_date: object,
    *,
    today: dt.date | None = None,
) -> str:
    cleaned = str(analysis_date or "").strip()
    try:
        parsed = dt.datetime.strptime(cleaned, "%Y-%m-%d").date()
    except ValueError as exc:
        raise RunRequestValidationError(
            [ValidationIssue("analysis_date", "Please enter a valid date in YYYY-MM-DD format.")]
        ) from exc

    reference_day = today or dt.date.today()
    if parsed > reference_day:
        raise RunRequestValidationError(
            [ValidationIssue("analysis_date", "Analysis date cannot be in the future.")]
        )

    return parsed.isoformat()


def normalize_output_language(output_language: object) -> str:
    normalized = str(output_language or "").strip()
    if not normalized:
        raise RunRequestValidationError(
            [ValidationIssue("output_language", "Output language is required.")]
        )
    return normalized


def validate_run_request(raw_request: dict) -> RunRequest:
    issues: List[ValidationIssue] = []

    ticker = _collect_issue(issues, lambda: normalize_ticker_symbol(raw_request.get("ticker", "")))
    analysis_date = _collect_issue(
        issues,
        lambda: normalize_analysis_date(raw_request.get("analysis_date", "")),
    )
    provider = _collect_issue(
        issues,
        lambda: _normalize_provider(raw_request.get("llm_provider", "")),
    )
    analysts = _collect_issue(
        issues,
        lambda: _normalize_analysts(raw_request.get("analysts", [])),
    )
    research_depth = _collect_issue(
        issues,
        lambda: _normalize_research_depth(raw_request.get("research_depth")),
    )
    output_language = _collect_issue(
        issues,
        lambda: normalize_output_language(
            raw_request.get("output_language", DEFAULT_OUTPUT_LANGUAGE)
        ),
    )

    shallow_thinker = str(raw_request.get("shallow_thinker", "")).strip()
    if not shallow_thinker:
        issues.append(ValidationIssue("shallow_thinker", "Quick-thinking model is required."))

    deep_thinker = str(raw_request.get("deep_thinker", "")).strip()
    if not deep_thinker:
        issues.append(ValidationIssue("deep_thinker", "Deep-thinking model is required."))

    google_thinking_level = _normalize_optional_str(raw_request.get(GOOGLE_THINKING_LEVEL_FIELD))
    openai_reasoning_effort = _normalize_optional_str(raw_request.get(OPENAI_REASONING_EFFORT_FIELD))
    anthropic_effort = _normalize_optional_str(raw_request.get(ANTHROPIC_EFFORT_FIELD))

    if provider is not None:
        backend_url = _normalize_backend_url(raw_request.get("backend_url"), provider)
        issues.extend(
            _validate_provider_specific_fields(
                provider=provider,
                google_thinking_level=google_thinking_level,
                openai_reasoning_effort=openai_reasoning_effort,
                anthropic_effort=anthropic_effort,
            )
        )

        if shallow_thinker and not validate_model(provider.value, shallow_thinker):
            issues.append(
                ValidationIssue(
                    "shallow_thinker",
                    f"Model '{shallow_thinker}' is not supported for provider '{provider.value}'.",
                )
            )
        if deep_thinker and not validate_model(provider.value, deep_thinker):
            issues.append(
                ValidationIssue(
                    "deep_thinker",
                    f"Model '{deep_thinker}' is not supported for provider '{provider.value}'.",
                )
            )
    else:
        backend_url = str(raw_request.get("backend_url", "")).strip()

    if issues:
        raise RunRequestValidationError(issues)

    return RunRequest(
        ticker=ticker,
        analysis_date=analysis_date,
        research_depth=research_depth,
        llm_provider=provider,
        backend_url=backend_url,
        shallow_thinker=shallow_thinker,
        deep_thinker=deep_thinker,
        analysts=analysts,
        google_thinking_level=google_thinking_level,
        openai_reasoning_effort=openai_reasoning_effort,
        anthropic_effort=anthropic_effort,
        output_language=output_language,
    )


def _collect_issue(issues: List[ValidationIssue], func):
    try:
        return func()
    except RunRequestValidationError as exc:
        issues.extend(exc.issues)
        return None


def _normalize_provider(provider: str | ProviderName) -> ProviderName:
    try:
        return ProviderName(str(provider).strip().lower())
    except ValueError as exc:
        raise RunRequestValidationError(
            [ValidationIssue("llm_provider", "Unsupported provider selected.")]
        ) from exc


def _normalize_analysts(analysts: Iterable[object]) -> List[AnalystKey]:
    normalized = []
    for analyst in analysts:
        try:
            value = analyst.value if hasattr(analyst, "value") else analyst
            normalized.append(AnalystKey(str(value).strip().lower()))
        except ValueError as exc:
            raise RunRequestValidationError(
                [ValidationIssue("analysts", f"Unsupported analyst '{analyst}'.")]
            ) from exc

    if not normalized:
        raise RunRequestValidationError(
            [ValidationIssue("analysts", "You must select at least one analyst.")]
        )

    return normalized


def _normalize_research_depth(research_depth: object) -> int:
    try:
        normalized = int(research_depth)
    except (TypeError, ValueError) as exc:
        raise RunRequestValidationError(
            [ValidationIssue("research_depth", "Research depth must be a supported value.")]
        ) from exc

    if normalized not in SUPPORTED_RESEARCH_DEPTHS:
        raise RunRequestValidationError(
            [ValidationIssue("research_depth", "Research depth must be a supported value.")]
        )

    return normalized


def _normalize_backend_url(backend_url: object, provider: ProviderName) -> str:
    normalized = str(backend_url or "").strip()
    if normalized:
        return normalized
    return get_provider_option(provider).backend_url


def _normalize_optional_str(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _validate_provider_specific_fields(
    *,
    provider: ProviderName,
    google_thinking_level: str | None,
    openai_reasoning_effort: str | None,
    anthropic_effort: str | None,
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    if provider != ProviderName.GOOGLE and google_thinking_level is not None:
        issues.append(
            ValidationIssue(
                GOOGLE_THINKING_LEVEL_FIELD,
                "Google thinking level is only supported for the Google provider.",
            )
        )
    if provider != ProviderName.OPENAI and openai_reasoning_effort is not None:
        issues.append(
            ValidationIssue(
                OPENAI_REASONING_EFFORT_FIELD,
                "OpenAI reasoning effort is only supported for the OpenAI provider.",
            )
        )
    if provider != ProviderName.ANTHROPIC and anthropic_effort is not None:
        issues.append(
            ValidationIssue(
                ANTHROPIC_EFFORT_FIELD,
                "Anthropic effort is only supported for the Anthropic provider.",
            )
        )

    return issues
