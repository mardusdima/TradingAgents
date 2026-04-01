import datetime as dt
import tempfile
import unittest
from pathlib import Path

from tradingagents.runtime.reporting import (
    compile_complete_report,
    export_report_bundle,
)


SAMPLE_FINAL_STATE = {
    "market_report": "Market report body",
    "sentiment_report": "Sentiment report body",
    "news_report": "News report body",
    "fundamentals_report": "Fundamentals report body",
    "investment_debate_state": {
        "bull_history": "Bull thesis",
        "bear_history": "Bear thesis",
        "judge_decision": "Research decision",
    },
    "trader_investment_plan": "Trader plan",
    "risk_debate_state": {
        "aggressive_history": "Aggressive risk",
        "conservative_history": "Conservative risk",
        "neutral_history": "Neutral risk",
        "judge_decision": "Portfolio decision",
    },
}


class RuntimeReportingTests(unittest.TestCase):
    def test_compile_complete_report_includes_all_major_sections(self):
        report = compile_complete_report(
            SAMPLE_FINAL_STATE,
            "SPY",
            generated_at=dt.datetime(2026, 4, 1, 9, 30, 0),
        )

        self.assertIn("# Trading Analysis Report: SPY", report)
        self.assertIn("Generated: 2026-04-01 09:30:00", report)
        self.assertIn("## I. Analyst Team Reports", report)
        self.assertIn("## II. Research Team Decision", report)
        self.assertIn("## III. Trading Team Plan", report)
        self.assertIn("## IV. Risk Management Team Decision", report)
        self.assertIn("## V. Portfolio Manager Decision", report)

    def test_export_report_bundle_writes_expected_structure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_path = Path(tmp_dir) / "exported_report"
            runtime_dir = Path(tmp_dir) / "runtime"
            runtime_reports_dir = runtime_dir / "reports"
            runtime_reports_dir.mkdir(parents=True)
            (runtime_reports_dir / "market_report.md").write_text(
                "Runtime market section",
                encoding="utf-8",
            )
            runtime_log_file = runtime_dir / "message_tool.log"
            runtime_log_file.write_text("runtime log line\n", encoding="utf-8")
            report_file = export_report_bundle(
                SAMPLE_FINAL_STATE,
                "SPY",
                save_path,
                generated_at=dt.datetime(2026, 4, 1, 9, 30, 0),
                runtime_report_dir=runtime_reports_dir,
                runtime_log_file=runtime_log_file,
            )

            self.assertTrue(report_file.exists())
            self.assertTrue((save_path / "1_analysts" / "market.md").exists())
            self.assertTrue((save_path / "2_research" / "manager.md").exists())
            self.assertTrue((save_path / "3_trading" / "trader.md").exists())
            self.assertTrue((save_path / "4_risk" / "neutral.md").exists())
            self.assertTrue((save_path / "5_portfolio" / "decision.md").exists())
            self.assertTrue((save_path / "reports" / "market_report.md").exists())
            self.assertEqual(
                (save_path / "reports" / "market_report.md").read_text(encoding="utf-8"),
                "Runtime market section",
            )
            self.assertTrue((save_path / "message_tool.log").exists())
            self.assertIn(
                "runtime log line",
                (save_path / "message_tool.log").read_text(encoding="utf-8"),
            )
            self.assertIn("Portfolio decision", report_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
