from __future__ import annotations

import ast
import datetime as dt
from collections import deque
from typing import Any, Callable, Deque, Dict, Iterable, Optional

from tradingagents.runtime.schemas import (
    AgentStatusSnapshot,
    EventType,
    RunLifecycleState,
    SessionEvent,
    SessionMessage,
    SessionSnapshot,
    StatsSnapshot,
    ToolCallSnapshot,
)

TimestampFactory = Callable[[], str]


class RuntimeSessionState:
    FIXED_AGENTS = {
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }

    ANALYST_MAPPING = {
        "market": "Market Analyst",
        "social": "Social Analyst",
        "news": "News Analyst",
        "fundamentals": "Fundamentals Analyst",
    }

    REPORT_SECTIONS = {
        "market_report": ("market", "Market Analyst"),
        "sentiment_report": ("social", "Social Analyst"),
        "news_report": ("news", "News Analyst"),
        "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
        "investment_plan": (None, "Research Manager"),
        "trader_investment_plan": (None, "Trader"),
        "final_trade_decision": (None, "Portfolio Manager"),
    }

    DISPLAY_SECTION_TITLES = {
        "market_report": "Market Analysis",
        "sentiment_report": "Social Sentiment",
        "news_report": "News Analysis",
        "fundamentals_report": "Fundamentals Analysis",
        "investment_plan": "Research Team Decision",
        "trader_investment_plan": "Trading Team Plan",
        "final_trade_decision": "Portfolio Management Decision",
    }

    STRUCTURED_SECTIONS = (
        "market_report",
        "sentiment_report",
        "news_report",
        "fundamentals_report",
        "bull_research",
        "bear_research",
        "investment_plan",
        "trader_investment_plan",
        "aggressive_risk",
        "neutral_risk",
        "conservative_risk",
        "final_trade_decision",
    )

    ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
    ANALYST_REPORT_MAP = {
        "market": "market_report",
        "social": "sentiment_report",
        "news": "news_report",
        "fundamentals": "fundamentals_report",
    }

    def __init__(
        self,
        max_length: int = 100,
        timestamp_factory: Optional[TimestampFactory] = None,
    ) -> None:
        self.messages: Deque[SessionMessage] = deque(maxlen=max_length)
        self.tool_calls: Deque[ToolCallSnapshot] = deque(maxlen=max_length)
        self.events: Deque[SessionEvent] = deque(maxlen=max_length * 4)
        self.current_report: str | None = None
        self.final_report: str | None = None
        self.agent_status: Dict[str, str] = {}
        self.current_agent: str | None = None
        self.report_sections: Dict[str, Optional[str]] = {}
        self.structured_report_sections: Dict[str, Optional[str]] = {}
        self.selected_analysts: list[str] = []
        self._last_message_id: str | None = None
        self._timestamp_factory = timestamp_factory or self._default_timestamp

    def _default_timestamp(self) -> str:
        return dt.datetime.now().strftime("%H:%M:%S")

    def init_for_analysis(self, selected_analysts: Iterable[Any]) -> None:
        self.selected_analysts = [self._normalize_analyst_key(a) for a in selected_analysts]

        self.agent_status = {}
        for analyst_key in self.selected_analysts:
            if analyst_key in self.ANALYST_MAPPING:
                self.agent_status[self.ANALYST_MAPPING[analyst_key]] = "pending"

        for team_agents in self.FIXED_AGENTS.values():
            for agent in team_agents:
                self.agent_status[agent] = "pending"

        self.report_sections = {}
        for section, (analyst_key, _) in self.REPORT_SECTIONS.items():
            if analyst_key is None or analyst_key in self.selected_analysts:
                self.report_sections[section] = None

        self.structured_report_sections = {}
        for section in self.STRUCTURED_SECTIONS:
            analyst_key = self._analyst_key_for_structured_section(section)
            if analyst_key is None or analyst_key in self.selected_analysts:
                self.structured_report_sections[section] = None

        self.current_report = None
        self.final_report = None
        self.current_agent = None
        self.messages.clear()
        self.tool_calls.clear()
        self.events.clear()
        self._last_message_id = None

    def start_run(self) -> None:
        if not self.selected_analysts:
            return
        first_agent = self.ANALYST_MAPPING[self.selected_analysts[0]]
        self.update_agent_status(first_agent, "in_progress")

    def get_completed_reports_count(self) -> int:
        count = 0
        for section in self.report_sections:
            _, finalizing_agent = self.REPORT_SECTIONS[section]
            has_content = self.report_sections.get(section) is not None
            agent_done = self.agent_status.get(finalizing_agent) == "completed"
            if has_content and agent_done:
                count += 1
        return count

    def add_message(
        self,
        message_type: str,
        content: str,
        *,
        source: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        timestamp = timestamp or self._timestamp_factory()
        message = SessionMessage(
            timestamp=timestamp,
            message_type=message_type,
            source=source,
            content=content,
        )
        self.messages.append(message)
        self._record_event(
            EventType.MESSAGE,
            timestamp=timestamp,
            source=source or message_type,
            payload={"message_type": message_type, "content": content},
        )

    def add_tool_call(
        self,
        tool_name: str,
        args: Any,
        *,
        source: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        timestamp = timestamp or self._timestamp_factory()
        tool_call = ToolCallSnapshot(
            tool_name=tool_name,
            arguments=args,
            timestamp=timestamp,
            source=source,
        )
        self.tool_calls.append(tool_call)
        self._record_event(
            EventType.TOOL_CALL,
            timestamp=timestamp,
            source=source,
            payload={"tool_name": tool_name, "arguments": args},
        )

    def update_agent_status(self, agent: str, status: str) -> None:
        if agent in self.agent_status:
            if self.agent_status.get(agent) == status:
                self.current_agent = agent
                return
            self.agent_status[agent] = status
            self.current_agent = agent
            self._record_event(
                EventType.STATUS_CHANGE,
                source=agent,
                payload={"status": status},
            )

    def update_report_section(
        self,
        section_name: str,
        content: str,
        *,
        structured_section: str | None = None,
    ) -> None:
        if section_name not in self.report_sections:
            return

        if structured_section:
            self.update_structured_report_section(structured_section, content)

        self.report_sections[section_name] = content
        self._record_event(
            EventType.REPORT_UPDATE,
            payload={"section": section_name, "content": content},
        )
        self._update_current_report(section_name)

    def update_structured_report_section(self, section_name: str, content: str) -> None:
        if section_name not in self.structured_report_sections:
            return
        self.structured_report_sections[section_name] = content

    def process_chunk(self, chunk: Dict[str, Any]) -> None:
        self._process_message_chunk(chunk)
        self._update_analyst_statuses(chunk)
        self._process_investment_debate_state(chunk)
        self._process_trader_plan(chunk)
        self._process_risk_debate_state(chunk)

    def apply_final_state(self, final_state: Dict[str, Any]) -> None:
        self._process_investment_debate_state(final_state)
        self._process_trader_plan(final_state)
        self._process_risk_debate_state(final_state)
        for section in self.report_sections:
            if final_state.get(section):
                structured_section = section if section in self.structured_report_sections else None
                self.update_report_section(
                    section,
                    final_state[section],
                    structured_section=structured_section,
                )

    def complete_run(self) -> None:
        for agent in self.agent_status:
            self.update_agent_status(agent, "completed")

    def to_snapshot(
        self,
        *,
        session_id: str | None = None,
        request: Any = None,
        selected_inputs: Dict[str, Any] | None = None,
        status: RunLifecycleState = RunLifecycleState.RUNNING,
        stats: Any = None,
        export_info: Any = None,
        errors: list[Any] | None = None,
    ) -> SessionSnapshot:
        return SessionSnapshot(
            session_id=session_id,
            request=request,
            selected_inputs=selected_inputs or {},
            status=status,
            agent_statuses=[
                AgentStatusSnapshot(name=name, status=state)
                for name, state in self.agent_status.items()
            ],
            events=list(self.events),
            messages=list(self.messages),
            tool_calls=list(self.tool_calls),
            current_report=self.current_report,
            report_sections=dict(self.report_sections),
            compiled_report=self.final_report,
            structured_report_sections=dict(self.structured_report_sections),
            stats=stats or StatsSnapshot(),
            export_info=export_info,
            errors=errors or [],
        )

    def _update_current_report(self, latest_section: str | None = None) -> None:
        latest_content = None
        if latest_section:
            latest_content = self.report_sections.get(latest_section)

        if latest_section and latest_content:
            title = self.DISPLAY_SECTION_TITLES.get(latest_section, latest_section)
            self.current_report = f"### {title}\n{latest_content}"

        self._update_final_report()

    def _update_final_report(self) -> None:
        report_parts = []

        analyst_sections = [
            ("market_report", "Market Analysis"),
            ("sentiment_report", "Social Sentiment"),
            ("news_report", "News Analysis"),
            ("fundamentals_report", "Fundamentals Analysis"),
        ]
        analyst_content = [
            f"### {title}\n{self.structured_report_sections[section]}"
            for section, title in analyst_sections
            if self.structured_report_sections.get(section)
        ]
        if analyst_content:
            report_parts.append("## Analyst Team Reports")
            report_parts.extend(analyst_content)

        research_content = []
        if self.structured_report_sections.get("bull_research"):
            research_content.append(
                f"### Bull Researcher Analysis\n{self.structured_report_sections['bull_research']}"
            )
        if self.structured_report_sections.get("bear_research"):
            research_content.append(
                f"### Bear Researcher Analysis\n{self.structured_report_sections['bear_research']}"
            )
        if self.structured_report_sections.get("investment_plan"):
            research_content.append(
                f"### Research Manager Decision\n{self.structured_report_sections['investment_plan']}"
            )
        if research_content:
            report_parts.append("## Research Team Decision")
            report_parts.extend(research_content)

        if self.structured_report_sections.get("trader_investment_plan"):
            report_parts.append("## Trading Team Plan")
            report_parts.append(self.structured_report_sections["trader_investment_plan"])

        risk_content = []
        if self.structured_report_sections.get("aggressive_risk"):
            risk_content.append(
                f"### Aggressive Analyst Analysis\n{self.structured_report_sections['aggressive_risk']}"
            )
        if self.structured_report_sections.get("conservative_risk"):
            risk_content.append(
                f"### Conservative Analyst Analysis\n{self.structured_report_sections['conservative_risk']}"
            )
        if self.structured_report_sections.get("neutral_risk"):
            risk_content.append(
                f"### Neutral Analyst Analysis\n{self.structured_report_sections['neutral_risk']}"
            )
        if risk_content:
            report_parts.append("## Risk Management Team Decision")
            report_parts.extend(risk_content)

        if self.structured_report_sections.get("final_trade_decision"):
            report_parts.append("## Portfolio Management Decision")
            report_parts.append(
                f"### Portfolio Manager Decision\n{self.structured_report_sections['final_trade_decision']}"
            )

        self.final_report = "\n\n".join(report_parts) if report_parts else None

    def _record_event(
        self,
        event_type: EventType,
        *,
        timestamp: str | None = None,
        source: str | None = None,
        payload: Dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            SessionEvent(
                event_type=event_type,
                timestamp=timestamp or self._timestamp_factory(),
                source=source,
                payload=payload or {},
            )
        )

    def _normalize_analyst_key(self, analyst: Any) -> str:
        return str(getattr(analyst, "value", analyst)).lower()

    def _analyst_key_for_structured_section(self, section_name: str) -> str | None:
        for analyst_key, report_section in self.ANALYST_REPORT_MAP.items():
            if section_name == report_section:
                return analyst_key
        return None

    def _process_message_chunk(self, chunk: Dict[str, Any]) -> None:
        messages = chunk.get("messages") or []
        if not messages:
            return

        last_message = messages[-1]
        msg_id = getattr(last_message, "id", None)
        if msg_id is not None and msg_id == self._last_message_id:
            return

        self._last_message_id = msg_id
        msg_type, content = classify_message_type(last_message)
        if content and content.strip():
            self.add_message(msg_type, content)

        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                if isinstance(tool_call, dict):
                    self.add_tool_call(tool_call["name"], tool_call["args"])
                else:
                    self.add_tool_call(tool_call.name, tool_call.args)

    def _update_analyst_statuses(self, chunk: Dict[str, Any]) -> None:
        found_active = False
        for analyst_key in self.ANALYST_ORDER:
            if analyst_key not in self.selected_analysts:
                continue

            agent_name = self.ANALYST_MAPPING[analyst_key]
            report_key = self.ANALYST_REPORT_MAP[analyst_key]

            if chunk.get(report_key):
                self.update_report_section(
                    report_key,
                    chunk[report_key],
                    structured_section=report_key,
                )

            has_report = bool(self.report_sections.get(report_key))
            if has_report:
                self.update_agent_status(agent_name, "completed")
            elif not found_active:
                self.update_agent_status(agent_name, "in_progress")
                found_active = True
            else:
                self.update_agent_status(agent_name, "pending")

        if not found_active and self.selected_analysts:
            if self.agent_status.get("Bull Researcher") == "pending":
                self.update_agent_status("Bull Researcher", "in_progress")

    def _set_research_team_status(self, status: str) -> None:
        for agent in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
            self.update_agent_status(agent, status)

    def _process_investment_debate_state(self, chunk: Dict[str, Any]) -> None:
        debate_state = chunk.get("investment_debate_state")
        if not debate_state:
            return

        bull_hist = debate_state.get("bull_history", "").strip()
        bear_hist = debate_state.get("bear_history", "").strip()
        judge = debate_state.get("judge_decision", "").strip()

        if bull_hist or bear_hist:
            self._set_research_team_status("in_progress")
        if bull_hist:
            self.update_structured_report_section("bull_research", bull_hist)
            self.update_report_section(
                "investment_plan",
                f"### Bull Researcher Analysis\n{bull_hist}",
            )
        if bear_hist:
            self.update_structured_report_section("bear_research", bear_hist)
            self.update_report_section(
                "investment_plan",
                f"### Bear Researcher Analysis\n{bear_hist}",
            )
        if judge:
            self.update_structured_report_section("investment_plan", judge)
            self.update_report_section(
                "investment_plan",
                f"### Research Manager Decision\n{judge}",
            )
            self._set_research_team_status("completed")
            self.update_agent_status("Trader", "in_progress")

    def _process_trader_plan(self, chunk: Dict[str, Any]) -> None:
        trader_plan = chunk.get("trader_investment_plan")
        if not trader_plan:
            return

        self.update_report_section(
            "trader_investment_plan",
            trader_plan,
            structured_section="trader_investment_plan",
        )
        if self.agent_status.get("Trader") != "completed":
            self.update_agent_status("Trader", "completed")
            self.update_agent_status("Aggressive Analyst", "in_progress")

    def _process_risk_debate_state(self, chunk: Dict[str, Any]) -> None:
        risk_state = chunk.get("risk_debate_state")
        if not risk_state:
            return

        agg_hist = risk_state.get("aggressive_history", "").strip()
        con_hist = risk_state.get("conservative_history", "").strip()
        neu_hist = risk_state.get("neutral_history", "").strip()
        judge = risk_state.get("judge_decision", "").strip()

        if agg_hist:
            if self.agent_status.get("Aggressive Analyst") != "completed":
                self.update_agent_status("Aggressive Analyst", "in_progress")
            self.update_structured_report_section("aggressive_risk", agg_hist)
            self.update_report_section(
                "final_trade_decision",
                f"### Aggressive Analyst Analysis\n{agg_hist}",
            )
        if con_hist:
            if self.agent_status.get("Conservative Analyst") != "completed":
                self.update_agent_status("Conservative Analyst", "in_progress")
            self.update_structured_report_section("conservative_risk", con_hist)
            self.update_report_section(
                "final_trade_decision",
                f"### Conservative Analyst Analysis\n{con_hist}",
            )
        if neu_hist:
            if self.agent_status.get("Neutral Analyst") != "completed":
                self.update_agent_status("Neutral Analyst", "in_progress")
            self.update_structured_report_section("neutral_risk", neu_hist)
            self.update_report_section(
                "final_trade_decision",
                f"### Neutral Analyst Analysis\n{neu_hist}",
            )
        if judge and self.agent_status.get("Portfolio Manager") != "completed":
            self.update_agent_status("Portfolio Manager", "in_progress")
            self.update_structured_report_section("final_trade_decision", judge)
            self.update_report_section(
                "final_trade_decision",
                f"### Portfolio Manager Decision\n{judge}",
            )
            self.update_agent_status("Aggressive Analyst", "completed")
            self.update_agent_status("Conservative Analyst", "completed")
            self.update_agent_status("Neutral Analyst", "completed")
            self.update_agent_status("Portfolio Manager", "completed")


def extract_content_string(content: Any) -> str | None:
    def is_empty(value: Any) -> bool:
        if value is None or value == "":
            return True
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return True
            try:
                return not bool(ast.literal_eval(stripped))
            except (ValueError, SyntaxError):
                return False
        return not bool(value)

    if is_empty(content):
        return None
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        text = content.get("text", "")
        return text.strip() if not is_empty(text) else None
    if isinstance(content, list):
        text_parts = [
            item.get("text", "").strip()
            if isinstance(item, dict) and item.get("type") == "text"
            else (item.strip() if isinstance(item, str) else "")
            for item in content
        ]
        result = " ".join(part for part in text_parts if part and not is_empty(part))
        return result or None
    return str(content).strip() if not is_empty(content) else None


def classify_message_type(message: Any) -> tuple[str, str | None]:
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    content = extract_content_string(getattr(message, "content", None))
    if isinstance(message, HumanMessage):
        if content and content.strip() == "Continue":
            return ("Control", content)
        return ("User", content)
    if isinstance(message, ToolMessage):
        return ("Data", content)
    if isinstance(message, AIMessage):
        return ("Agent", content)
    return ("System", content)
