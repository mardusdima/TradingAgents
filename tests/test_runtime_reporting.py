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
            report_file = export_report_bundle(
                SAMPLE_FINAL_STATE,
                "SPY",
                save_path,
                generated_at=dt.datetime(2026, 4, 1, 9, 30, 0),
            )

            self.assertTrue(report_file.exists())
            self.assertTrue((save_path / "1_analysts" / "market.md").exists())
            self.assertTrue((save_path / "2_research" / "manager.md").exists())
            self.assertTrue((save_path / "3_trading" / "trader.md").exists())
            self.assertTrue((save_path / "4_risk" / "neutral.md").exists())
            self.assertTrue((save_path / "5_portfolio" / "decision.md").exists())
            self.assertIn("Portfolio decision", report_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
