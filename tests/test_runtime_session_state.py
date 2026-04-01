import unittest

from langchain_core.messages import AIMessage

from tradingagents.runtime.schemas import EventType, RunLifecycleState
from tradingagents.runtime.session_state import RuntimeSessionState


class RuntimeSessionStateTests(unittest.TestCase):
    def setUp(self):
        self.state = RuntimeSessionState(timestamp_factory=lambda: "12:00:00")

    def test_analyst_chunk_updates_status_messages_and_report_views(self):
        self.state.init_for_analysis(["market", "news"])
        self.state.start_run()

        self.state.process_chunk(
            {
                "messages": [AIMessage(content="Starting market analysis", id="msg-1")],
                "market_report": "Market report content",
            }
        )

        self.assertEqual(self.state.agent_status["Market Analyst"], "completed")
        self.assertEqual(self.state.agent_status["News Analyst"], "in_progress")
        self.assertEqual(self.state.messages[0].message_type, "Agent")
        self.assertEqual(self.state.messages[0].content, "Starting market analysis")
        self.assertEqual(
            self.state.structured_report_sections["market_report"],
            "Market report content",
        )
        self.assertIn("### Market Analysis", self.state.current_report)

        self.state.process_chunk(
            {
                "messages": [AIMessage(content="Starting market analysis", id="msg-1")],
                "market_report": "Market report content",
            }
        )
        self.assertEqual(len(self.state.messages), 1)

    def test_debate_trader_and_risk_chunks_accumulate_structured_reports(self):
        self.state.init_for_analysis(["market"])
        self.state.start_run()
        self.state.process_chunk({"market_report": "Market report content"})

        self.state.process_chunk(
            {
                "investment_debate_state": {
                    "bull_history": "Bull case",
                    "bear_history": "Bear case",
                    "judge_decision": "Research decision",
                }
            }
        )
        self.assertEqual(self.state.structured_report_sections["bull_research"], "Bull case")
        self.assertEqual(self.state.structured_report_sections["bear_research"], "Bear case")
        self.assertEqual(self.state.structured_report_sections["investment_plan"], "Research decision")
        self.assertEqual(self.state.agent_status["Research Manager"], "completed")
        self.assertEqual(self.state.agent_status["Trader"], "in_progress")

        self.state.process_chunk({"trader_investment_plan": "Trader plan"})
        self.assertEqual(self.state.structured_report_sections["trader_investment_plan"], "Trader plan")
        self.assertEqual(self.state.agent_status["Trader"], "completed")
        self.assertEqual(self.state.agent_status["Aggressive Analyst"], "in_progress")

        self.state.process_chunk(
            {
                "risk_debate_state": {
                    "aggressive_history": "Aggressive stance",
                    "conservative_history": "Conservative stance",
                    "neutral_history": "Neutral stance",
                    "judge_decision": "Portfolio decision",
                }
            }
        )

        self.assertEqual(self.state.structured_report_sections["aggressive_risk"], "Aggressive stance")
        self.assertEqual(self.state.structured_report_sections["conservative_risk"], "Conservative stance")
        self.assertEqual(self.state.structured_report_sections["neutral_risk"], "Neutral stance")
        self.assertEqual(self.state.structured_report_sections["final_trade_decision"], "Portfolio decision")
        self.assertEqual(self.state.agent_status["Portfolio Manager"], "completed")
        self.assertIn("Bull Researcher Analysis", self.state.final_report)
        self.assertIn("Trader plan", self.state.final_report)
        self.assertIn("Portfolio Manager Decision", self.state.final_report)
        self.assertEqual(self.state.get_completed_reports_count(), 4)

    def test_snapshot_contains_structured_history_and_events(self):
        self.state.init_for_analysis(["market"])
        self.state.add_message("System", "Hello", source="cli")
        self.state.add_tool_call("get_stock_data", {"ticker": "SPY"}, source="Market Analyst")
        self.state.update_agent_status("Market Analyst", "in_progress")
        self.state.update_report_section(
            "market_report",
            "Market content",
            structured_section="market_report",
        )

        snapshot = self.state.to_snapshot(
            selected_inputs={"ticker": "SPY"},
            status=RunLifecycleState.RUNNING,
        )

        self.assertEqual(snapshot.messages[0].message_type, "System")
        self.assertEqual(snapshot.tool_calls[0].tool_name, "get_stock_data")
        self.assertEqual(snapshot.agent_statuses[0].name, "Market Analyst")
        self.assertEqual(snapshot.structured_report_sections["market_report"], "Market content")
        self.assertEqual(
            [event.event_type for event in snapshot.events],
            [
                EventType.MESSAGE,
                EventType.TOOL_CALL,
                EventType.STATUS_CHANGE,
                EventType.REPORT_UPDATE,
            ],
        )


if __name__ == "__main__":
    unittest.main()
