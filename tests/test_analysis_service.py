import threading
import time
import tempfile
import unittest
from pathlib import Path

from tradingagents.app.history import AnalysisHistoryRepository
from tradingagents.app.models import AnalysisRequest, RunStats
from tradingagents.app.service import AnalysisRunService, SingleRunCoordinator


class FakeBackend:
    def __init__(self, chunks, *, should_fail=False, pause_event=None, stats=None):
        self.chunks = chunks
        self.should_fail = should_fail
        self.pause_event = pause_event
        self.stats = stats or RunStats()

    def stream(self, request):
        for chunk in self.chunks:
            yield chunk
        if self.pause_event is not None:
            self.pause_event.wait(timeout=5)
        if self.should_fail:
            raise RuntimeError("backend exploded")

    def get_stats(self):
        return self.stats


class AnalysisRunServiceTests(unittest.TestCase):
    def make_request(self):
        return AnalysisRequest(
            ticker="SPY",
            analysis_date="2026-03-31",
            analysts=["market", "news"],
            research_depth=1,
            llm_provider="openai",
            backend_url="https://api.openai.com/v1",
            shallow_thinker="gpt-5.4-mini",
            deep_thinker="gpt-5.4",
            openai_reasoning_effort="medium",
            output_language="English",
        )

    def test_service_marks_run_completed_and_extracts_rating(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            backend = FakeBackend(
                [
                    {"market_report": "Market says sell"},
                    {"trader_investment_plan": "Trader plan"},
                    {"final_trade_decision": "**Rating**: SELL"},
                ]
            )
            service = AnalysisRunService(repository, backend_factory=lambda request: backend)

            detail = service.run_sync(self.make_request(), source="ui")

            self.assertEqual(detail.summary.status, "completed")
            self.assertEqual(detail.summary.rating, "SELL")
            self.assertEqual(detail.sections["market_report"], "Market says sell")
            self.assertEqual(detail.sections["trader_investment_plan"], "Trader plan")
            self.assertEqual(detail.sections["final_trade_decision"], "**Rating**: SELL")

    def test_service_marks_run_failed_when_backend_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            backend = FakeBackend([{"market_report": "Partial report"}], should_fail=True)
            service = AnalysisRunService(repository, backend_factory=lambda request: backend)

            detail = service.run_sync(self.make_request(), source="ui")

            self.assertEqual(detail.summary.status, "failed")
            self.assertIn("backend exploded", detail.summary.error_message)
            self.assertEqual(detail.sections["market_report"], "Partial report")

    def test_service_notifies_listener_for_each_stream_chunk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            backend = FakeBackend(
                [
                    {"market_report": "Market says hold"},
                    {"final_trade_decision": "**Rating**: HOLD"},
                ]
            )
            service = AnalysisRunService(repository, backend_factory=lambda request: backend)
            seen_chunks = []

            created = service.create_pending_run(self.make_request(), source="cli")
            service.execute_run(created.run_id, self.make_request(), on_chunk=seen_chunks.append)

            self.assertEqual(seen_chunks, backend.chunks)

    def test_service_persists_backend_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            backend = FakeBackend(
                [{"final_trade_decision": "**Rating**: BUY"}],
                stats=RunStats(llm_calls=4, tool_calls=2, tokens_in=150, tokens_out=90),
            )
            service = AnalysisRunService(repository, backend_factory=lambda request: backend)

            detail = service.run_sync(self.make_request(), source="ui")

            self.assertEqual(detail.stats.llm_calls, 4)
            self.assertEqual(detail.stats.tool_calls, 2)
            self.assertEqual(detail.stats.tokens_in, 150)
            self.assertEqual(detail.stats.tokens_out, 90)


class SingleRunCoordinatorTests(unittest.TestCase):
    def make_request(self):
        return AnalysisRequest(
            ticker="NVDA",
            analysis_date="2026-03-31",
            analysts=["market"],
            research_depth=1,
            llm_provider="openai",
            backend_url="https://api.openai.com/v1",
            shallow_thinker="gpt-5.4-mini",
            deep_thinker="gpt-5.4",
            openai_reasoning_effort="medium",
            output_language="English",
        )

    def test_coordinator_allows_only_one_active_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repository = AnalysisHistoryRepository(Path(tmpdir) / "results")
            pause_event = threading.Event()
            service = AnalysisRunService(
                repository,
                backend_factory=lambda request: FakeBackend(
                    [{"market_report": "In progress"}],
                    pause_event=pause_event,
                ),
            )
            coordinator = SingleRunCoordinator(service)

            run_id = coordinator.start(self.make_request(), source="ui")

            deadline = time.time() + 5
            while coordinator.active_run_id != run_id and time.time() < deadline:
                time.sleep(0.01)

            with self.assertRaises(RuntimeError):
                coordinator.start(self.make_request(), source="ui")

            pause_event.set()

            deadline = time.time() + 5
            while coordinator.active_run_id is not None and time.time() < deadline:
                time.sleep(0.01)

            detail = repository.get_run_detail(run_id)
            self.assertEqual(detail.summary.status, "completed")


if __name__ == "__main__":
    unittest.main()
