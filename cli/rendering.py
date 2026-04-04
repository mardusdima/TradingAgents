from __future__ import annotations

from typing import Dict, List, Tuple

from tradingagents.runtime.schemas import SessionSnapshot

TEAM_AGENT_ORDER = {
    "Analyst Team": [
        "Market Analyst",
        "Social Analyst",
        "News Analyst",
        "Fundamentals Analyst",
    ],
    "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
    "Trading Team": ["Trader"],
    "Risk Management": [
        "Aggressive Analyst",
        "Neutral Analyst",
        "Conservative Analyst",
    ],
    "Portfolio Management": ["Portfolio Manager"],
}

REPORT_FINALIZERS = {
    "market_report": "Market Analyst",
    "sentiment_report": "Social Analyst",
    "news_report": "News Analyst",
    "fundamentals_report": "Fundamentals Analyst",
    "investment_plan": "Research Manager",
    "trader_investment_plan": "Trader",
    "final_trade_decision": "Portfolio Manager",
}


def get_agent_status_map(snapshot: SessionSnapshot) -> Dict[str, str]:
    return {status.name: status.status for status in snapshot.agent_statuses}


def get_team_status_rows(snapshot: SessionSnapshot) -> List[Tuple[str, str, str]]:
    agent_statuses = get_agent_status_map(snapshot)
    rows: List[Tuple[str, str, str]] = []

    for team_name, agents in TEAM_AGENT_ORDER.items():
        active_agents = [agent for agent in agents if agent in agent_statuses]
        if not active_agents:
            continue

        for index, agent in enumerate(active_agents):
            rows.append(
                (
                    team_name if index == 0 else "",
                    agent,
                    agent_statuses.get(agent, "pending"),
                )
            )
        rows.append(("─" * 20, "─" * 20, "─" * 20))

    return rows


def get_recent_activity_rows(
    snapshot: SessionSnapshot,
    *,
    max_rows: int = 12,
    max_content_length: int = 200,
) -> List[Tuple[str, str, str]]:
    activity_rows: List[Tuple[str, str, str]] = []

    for tool_call in snapshot.tool_calls:
        formatted_args = format_tool_args(tool_call.arguments)
        activity_rows.append(
            (
                tool_call.timestamp or "",
                "Tool",
                f"{tool_call.tool_name}: {formatted_args}",
            )
        )

    for message in snapshot.messages:
        content = str(message.content or "")
        if len(content) > max_content_length:
            content = content[: max_content_length - 3] + "..."
        activity_rows.append((message.timestamp or "", message.message_type, content))

    activity_rows.sort(key=lambda row: row[0], reverse=True)
    return activity_rows[:max_rows]


def get_completed_reports_count(snapshot: SessionSnapshot) -> int:
    agent_statuses = get_agent_status_map(snapshot)
    count = 0

    for section_name, content in snapshot.report_sections.items():
        finalizing_agent = REPORT_FINALIZERS.get(section_name)
        if not finalizing_agent:
            continue
        if content is not None and agent_statuses.get(finalizing_agent) == "completed":
            count += 1

    return count


def format_tool_args(args, max_length: int = 80) -> str:
    result = str(args)
    if len(result) > max_length:
        return result[: max_length - 3] + "..."
    return result
