import unittest

from cli.rendering import (
    get_completed_reports_count,
    get_recent_activity_rows,
    get_team_status_rows,
)
from tradingagents.runtime.schemas import (
    AgentStatusSnapshot,
    SessionMessage,
    SessionSnapshot,
    StatsSnapshot,
    ToolCallSnapshot,
)


class CliRenderingTests(unittest.TestCase):
    def test_team_status_rows_follow_cli_team_order(self):
        snapshot = SessionSnapshot(
            agent_statuses=[
                AgentStatusSnapshot(name="News Analyst", status="pending"),
                AgentStatusSnapshot(name="Market Analyst", status="completed"),
                AgentStatusSnapshot(name="Bull Researcher", status="in_progress"),
                AgentStatusSnapshot(name="Bear Researcher", status="pending"),
                AgentStatusSnapshot(name="Research Manager", status="pending"),
            ]
        )

        rows = get_team_status_rows(snapshot)

        self.assertEqual(rows[0], ("Analyst Team", "Market Analyst", "completed"))
        self.assertEqual(rows[1], ("", "News Analyst", "pending"))
        self.assertEqual(rows[2], ("────────────────────", "────────────────────", "────────────────────"))
        self.assertEqual(rows[3], ("Research Team", "Bull Researcher", "in_progress"))

    def test_recent_activity_rows_merge_messages_and_tool_calls_by_latest_timestamp(self):
        snapshot = SessionSnapshot(
            messages=[
                SessionMessage(timestamp="12:00:01", message_type="Agent", content="Older"),
                SessionMessage(timestamp="12:00:03", message_type="System", content="Newest"),
            ],
            tool_calls=[
                ToolCallSnapshot(
                    timestamp="12:00:02",
                    tool_name="get_stock_data",
                    arguments={"ticker": "SPY"},
                )
            ],
        )

        rows = get_recent_activity_rows(snapshot)

        self.assertEqual(rows[0], ("12:00:03", "System", "Newest"))
        self.assertEqual(rows[1][0:2], ("12:00:02", "Tool"))
        self.assertIn("get_stock_data", rows[1][2])
        self.assertEqual(rows[2], ("12:00:01", "Agent", "Older"))

    def test_completed_reports_count_requires_agent_completion(self):
        snapshot = SessionSnapshot(
            agent_statuses=[
                AgentStatusSnapshot(name="Market Analyst", status="completed"),
                AgentStatusSnapshot(name="Research Manager", status="in_progress"),
            ],
            report_sections={
                "market_report": "Market content",
                "investment_plan": "Research content",
            },
            stats=StatsSnapshot(),
        )

        self.assertEqual(get_completed_reports_count(snapshot), 1)


if __name__ == "__main__":
    unittest.main()
