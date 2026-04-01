from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ProviderName(str, Enum):
    OPENAI = "openai"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"
    XAI = "xai"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"


class AnalystKey(str, Enum):
    MARKET = "market"
    SOCIAL = "social"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"


class AgentName(str, Enum):
    MARKET_ANALYST = "Market Analyst"
    SOCIAL_ANALYST = "Social Analyst"
    NEWS_ANALYST = "News Analyst"
    FUNDAMENTALS_ANALYST = "Fundamentals Analyst"
    BULL_RESEARCHER = "Bull Researcher"
    BEAR_RESEARCHER = "Bear Researcher"
    RESEARCH_MANAGER = "Research Manager"
    TRADER = "Trader"
    AGGRESSIVE_ANALYST = "Aggressive Analyst"
    NEUTRAL_ANALYST = "Neutral Analyst"
    CONSERVATIVE_ANALYST = "Conservative Analyst"
    PORTFOLIO_MANAGER = "Portfolio Manager"


class ReportSectionKey(str, Enum):
    MARKET_REPORT = "market_report"
    SENTIMENT_REPORT = "sentiment_report"
    NEWS_REPORT = "news_report"
    FUNDAMENTALS_REPORT = "fundamentals_report"
    BULL_RESEARCH = "bull_research"
    BEAR_RESEARCH = "bear_research"
    INVESTMENT_PLAN = "investment_plan"
    TRADER_INVESTMENT_PLAN = "trader_investment_plan"
    AGGRESSIVE_RISK = "aggressive_risk"
    NEUTRAL_RISK = "neutral_risk"
    CONSERVATIVE_RISK = "conservative_risk"
    FINAL_TRADE_DECISION = "final_trade_decision"


class EventType(str, Enum):
    SNAPSHOT = "snapshot"
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    REPORT_UPDATE = "report_update"
    STATUS_CHANGE = "status_change"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


class RunLifecycleState(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RunRequest:
    ticker: str
    analysis_date: str
    research_depth: int
    llm_provider: ProviderName
    backend_url: str
    shallow_thinker: str
    deep_thinker: str
    analysts: List[AnalystKey] = field(default_factory=list)
    google_thinking_level: Optional[str] = None
    openai_reasoning_effort: Optional[str] = None
    anthropic_effort: Optional[str] = None
    output_language: str = "English"


@dataclass
class AgentStatusSnapshot:
    name: str
    status: str


@dataclass
class SessionMessage:
    timestamp: Optional[str] = None
    message_type: str = "System"
    source: Optional[str] = None
    content: Optional[str] = None
    event_type: EventType = EventType.MESSAGE


@dataclass
class ToolCallSnapshot:
    tool_name: str
    arguments: Any = None
    timestamp: Optional[str] = None
    source: Optional[str] = None
    event_type: EventType = EventType.TOOL_CALL


@dataclass
class SessionEvent:
    event_type: EventType
    timestamp: Optional[str] = None
    source: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StatsSnapshot:
    llm_calls: int = 0
    tool_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ExportInfo:
    report_path: Optional[str] = None
    log_path: Optional[str] = None


@dataclass
class RunError:
    message: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class SessionSnapshot:
    session_id: Optional[str] = None
    request: Optional[RunRequest] = None
    selected_inputs: Dict[str, Any] = field(default_factory=dict)
    status: RunLifecycleState = RunLifecycleState.PENDING
    agent_statuses: List[AgentStatusSnapshot] = field(default_factory=list)
    events: List[SessionEvent] = field(default_factory=list)
    messages: List[SessionMessage] = field(default_factory=list)
    tool_calls: List[ToolCallSnapshot] = field(default_factory=list)
    current_report: Optional[str] = None
    report_sections: Dict[str, Optional[str]] = field(default_factory=dict)
    compiled_report: Optional[str] = None
    structured_report_sections: Dict[str, Optional[str]] = field(default_factory=dict)
    stats: StatsSnapshot = field(default_factory=StatsSnapshot)
    export_info: ExportInfo = field(default_factory=ExportInfo)
    errors: List[RunError] = field(default_factory=list)
