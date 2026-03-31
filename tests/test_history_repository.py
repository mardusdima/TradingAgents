import tempfile
import unittest
from pathlib import Path

from tradingagents.app.history import AnalysisHistoryRepository
from tradingagents.app.models import AnalysisRequest, RunStats


class AnalysisHistoryRepositoryTests(unittest.TestCase):
    def test_repository_persists_run_sections_events_stats_and_complete_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results_dir = Path(tmpdir) / "results"
            repository = AnalysisHistoryRepository(results_dir)
            request = AnalysisRequest(
                ticker="SPY",
                analysis_date="2026-03-31",
                analysts=["market", "news"],
                research_depth=3,
                llm_provider="openai",
                backend_url="https://api.openai.com/v1",
                shallow_thinker="gpt-5.4-mini",
                deep_thinker="gpt-5.4",
                openai_reasoning_effort="medium",
                output_language="English",
            )

            created = repository.create_run(request, source="ui")
            repository.mark_running(created.run_id)
            repository.record_event(
                created.run_id,
                event_type="message",
                message_type="System",
                content="Selected ticker: SPY",
            )
            repository.upsert_section(
                created.run_id,
                section_key="market_report",
                content="Market report body",
            )
            repository.upsert_section(
                created.run_id,
                section_key="final_trade_decision",
                content="**Rating**: BUY",
            )
            repository.update_stats(
                created.run_id,
                RunStats(llm_calls=3, tool_calls=2, tokens_in=111, tokens_out=222),
            )
            repository.mark_completed(created.run_id, rating="BUY")

            detail = repository.get_run_detail(created.run_id)

            self.assertEqual(detail.summary.status, "completed")
            self.assertEqual(detail.summary.rating, "BUY")
            self.assertEqual(detail.summary.source, "ui")
            self.assertEqual(detail.sections["market_report"], "Market report body")
            self.assertEqual(detail.sections["final_trade_decision"], "**Rating**: BUY")
            self.assertEqual(detail.stats.tokens_out, 222)
            self.assertEqual(len(detail.events), 1)

            artifact_dir = results_dir / "runs" / created.run_id
            complete_report = artifact_dir / "complete_report.md"
            self.assertTrue(complete_report.exists())
            self.assertIn("# Trading Analysis Report: SPY", complete_report.read_text())
            self.assertTrue((results_dir / "history.db").exists())

    def test_repository_filters_history_by_ticker_status_and_rating(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results_dir = Path(tmpdir) / "results"
            repository = AnalysisHistoryRepository(results_dir)

            spy_run = repository.create_run(
                AnalysisRequest(
                    ticker="SPY",
                    analysis_date="2026-03-31",
                    analysts=["market"],
                    research_depth=1,
                    llm_provider="openai",
                    backend_url="https://api.openai.com/v1",
                    shallow_thinker="gpt-5.4-mini",
                    deep_thinker="gpt-5.4",
                    openai_reasoning_effort="medium",
                    output_language="English",
                ),
                source="ui",
            )
            repository.mark_completed(spy_run.run_id, rating="BUY")

            amzn_run = repository.create_run(
                AnalysisRequest(
                    ticker="AMZN",
                    analysis_date="2026-03-30",
                    analysts=["news"],
                    research_depth=1,
                    llm_provider="openai",
                    backend_url="https://api.openai.com/v1",
                    shallow_thinker="gpt-5.4-mini",
                    deep_thinker="gpt-5.4",
                    openai_reasoning_effort="medium",
                    output_language="English",
                ),
                source="legacy",
            )
            repository.mark_failed(amzn_run.run_id, error_message="boom")

            filtered = repository.list_runs(ticker="SPY", status="completed", rating="BUY")

            self.assertEqual([run.run_id for run in filtered], [spy_run.run_id])


if __name__ == "__main__":
    unittest.main()
