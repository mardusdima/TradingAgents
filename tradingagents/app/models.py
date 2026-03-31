from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


ANALYST_ORDER = ["market", "social", "news", "fundamentals"]


@dataclass
class AnalysisRequest:
    ticker: str
    analysis_date: str
    analysts: list[str]
    research_depth: int
    llm_provider: str
    backend_url: str
    shallow_thinker: str
    deep_thinker: str
    google_thinking_level: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None
    anthropic_effort: Optional[str] = None
    output_language: str = "English"

    def __post_init__(self) -> None:
        self.ticker = self.ticker.strip().upper()
        self.llm_provider = self.llm_provider.strip().lower()

        normalized = []
        seen = set()
        for analyst in self.analysts:
            key = analyst.strip().lower()
            if key and key not in seen:
                seen.add(key)
                normalized.append(key)

        ordered = [analyst for analyst in ANALYST_ORDER if analyst in normalized]
        extras = [analyst for analyst in normalized if analyst not in ANALYST_ORDER]
        self.analysts = ordered + extras

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunStats:
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class RunSummary:
    run_id: str
    ticker: str
    analysis_date: str
    status: str
    source: str
    request: AnalysisRequest
    rating: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    error_message: Optional[str] = None
    legacy_source_key: Optional[str] = None


@dataclass
class RunEvent:
    event_type: str
    message_type: Optional[str]
    content: str
    created_at: str


@dataclass
class RunDetail:
    summary: RunSummary
    sections: dict[str, str] = field(default_factory=dict)
    events: list[RunEvent] = field(default_factory=list)
    stats: RunStats = field(default_factory=RunStats)
    artifact_dir: Optional[str] = None
