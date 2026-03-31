import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from tradingagents.app.history import AnalysisHistoryRepository
from tradingagents.app.models import AnalysisRequest
from tradingagents.ui.main import create_app


class StubCoordinator:
    def __init__(self, run_id="run-new", error=None):
        self.run_id = run_id
        self.error = error
        self.started_requests = []
        self.active_run_id = None

    def start(self, request, *, source):
        if self.error:
            raise self.error
        self.started_requests.append((request, source))
        self.active_run_id = self.run_id
        return self.run_id


class WebUiTests(unittest.TestCase):
    def make_request(self, ticker="SPY", rating=None):
        request = AnalysisRequest(
            ticker=ticker,
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
        return request, rating

    def create_completed_run(self, repository, ticker="SPY", rating="BUY"):
        request, _ = self.make_request(ticker=ticker)
        created = repository.create_run(request, source="ui")
        repository.upsert_section(created.run_id, section_key="market_report", content=f"{ticker} market section")
        repository.upsert_section(created.run_id, section_key="final_trade_decision", content=f"**Rating**: {rating}")
        repository.mark_completed(created.run_id, rating=rating)
        return created.run_id

    def test_dashboard_renders_form_and_recent_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            run_id = self.create_completed_run(repository)
            client = TestClient(create_app(repository=repository, coordinator=StubCoordinator()))

            response = client.get("/")

            self.assertEqual(response.status_code, 200)
            self.assertIn('name="ticker"', response.text)
            self.assertIn("Start Analysis", response.text)
            self.assertIn(run_id, response.text)

    def test_start_run_redirects_to_detail_and_builds_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            coordinator = StubCoordinator(run_id="run-123")
            client = TestClient(create_app(repository=repository, coordinator=coordinator))

            response = client.post(
                "/runs",
                data={
                    "ticker": "spy",
                    "analysis_date": "2026-03-31",
                    "analysts": ["market", "news"],
                    "research_depth": "3",
                    "llm_provider": "openai",
                    "backend_url": "https://api.openai.com/v1",
                    "shallow_thinker": "gpt-5.4-mini",
                    "deep_thinker": "gpt-5.4",
                    "openai_reasoning_effort": "medium",
                    "output_language": "English",
                },
                follow_redirects=False,
            )

            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["location"], "/runs/run-123")
            request, source = coordinator.started_requests[0]
            self.assertEqual(source, "ui")
            self.assertEqual(request.ticker, "SPY")
            self.assertEqual(request.analysts, ["market", "news"])

    def test_start_run_surfaces_single_run_guard(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            coordinator = StubCoordinator(error=RuntimeError("An analysis is already running."))
            client = TestClient(create_app(repository=repository, coordinator=coordinator))

            response = client.post(
                "/runs",
                data={
                    "ticker": "SPY",
                    "analysis_date": "2026-03-31",
                    "analysts": ["market"],
                    "research_depth": "1",
                    "llm_provider": "openai",
                    "backend_url": "https://api.openai.com/v1",
                    "shallow_thinker": "gpt-5.4-mini",
                    "deep_thinker": "gpt-5.4",
                    "openai_reasoning_effort": "medium",
                    "output_language": "English",
                },
            )

            self.assertEqual(response.status_code, 409)
            self.assertIn("already running", response.text)

    def test_history_filters_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            self.create_completed_run(repository, ticker="SPY", rating="BUY")
            self.create_completed_run(repository, ticker="AMZN", rating="SELL")
            client = TestClient(create_app(repository=repository, coordinator=StubCoordinator()))

            response = client.get("/history?ticker=SPY&status=completed&rating=BUY")

            self.assertEqual(response.status_code, 200)
            self.assertIn("SPY", response.text)
            self.assertNotIn("AMZN", response.text)

    def test_run_detail_and_rerun_prefill_render_saved_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            run_id = self.create_completed_run(repository, ticker="SPY", rating="BUY")
            client = TestClient(create_app(repository=repository, coordinator=StubCoordinator()))

            detail_response = client.get(f"/runs/{run_id}")
            rerun_response = client.get(f"/runs/{run_id}/rerun")

            self.assertEqual(detail_response.status_code, 200)
            self.assertIn("SPY market section", detail_response.text)
            self.assertIn("**Rating**: BUY", detail_response.text)
            self.assertEqual(rerun_response.status_code, 200)
            self.assertIn('value="SPY"', rerun_response.text)
            self.assertIn('value="2026-03-31"', rerun_response.text)

    def test_status_fragment_renders_live_run_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            run_id = self.create_completed_run(repository, ticker="SPY", rating="BUY")
            client = TestClient(create_app(repository=repository, coordinator=StubCoordinator()))

            response = client.get(f"/runs/{run_id}/fragments/status")

            self.assertEqual(response.status_code, 200)
            self.assertIn("completed", response.text)
            self.assertIn("BUY", response.text)


if __name__ == "__main__":
    unittest.main()
