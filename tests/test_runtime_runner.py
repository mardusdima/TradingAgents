import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessage

from tradingagents.runtime.options import DEFAULT_BACKEND_URL
from tradingagents.runtime.runner import (
    RuntimeRunnerError,
    RuntimeRunnerHooks,
    TradingAgentsRuntimeRunner,
)
from tradingagents.runtime.schemas import AnalystKey, ProviderName, RunLifecycleState, RunRequest


class FakePropagator:
    def create_initial_state(self, ticker, analysis_date):
        return {"ticker": ticker, "analysis_date": analysis_date}

    def get_graph_args(self, callbacks=None):
        return {"callbacks": callbacks or []}


class FakeStreamGraph:
    def __init__(self, chunks, *, should_raise=False):
        self._chunks = chunks
        self._should_raise = should_raise

    def stream(self, init_agent_state, **kwargs):
        if self._should_raise:
            raise RuntimeError("stream failed")
        for chunk in self._chunks:
            yield chunk


class FakeTradingGraph:
    def __init__(self, selected_analysts, config=None, debug=False, callbacks=None):
        self.selected_analysts = selected_analysts
        self.config = config or {}
        self.debug = debug
        self.callbacks = callbacks or []
        self.propagator = FakePropagator()
        self.graph = FakeStreamGraph(
            [
                {
                    "messages": [
                        AIMessage(
                            content="Starting market analysis",
                            id="msg-1",
                            tool_calls=[
                                {
                                    "id": "tool-call-1",
                                    "name": "get_stock_data",
                                    "args": {"ticker": "SPY"},
                                }
                            ],
                        )
                    ],
                    "market_report": "Market report content",
                },
                {
                    "investment_debate_state": {
                        "bull_history": "Bull case",
                        "bear_history": "Bear case",
                        "judge_decision": "Research decision",
                    }
                },
                {"trader_investment_plan": "Trader plan"},
                {
                    "risk_debate_state": {
                        "aggressive_history": "Aggressive risk",
                        "conservative_history": "Conservative risk",
                        "neutral_history": "Neutral risk",
                        "judge_decision": "Portfolio decision",
                    },
                    "final_trade_decision": "BUY",
                },
            ]
        )

    def process_signal(self, full_signal):
        return f"processed:{full_signal}"


class FailingTradingGraph(FakeTradingGraph):
    def __init__(self, selected_analysts, config=None, debug=False, callbacks=None):
        super().__init__(selected_analysts, config=config, debug=debug, callbacks=callbacks)
        self.graph = FakeStreamGraph([], should_raise=True)


class RuntimeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.request = RunRequest(
            ticker="SPY",
            analysis_date="2026-03-31",
            analysts=[AnalystKey.MARKET],
            research_depth=1,
            llm_provider=ProviderName.OPENAI,
            backend_url=DEFAULT_BACKEND_URL,
            shallow_thinker="gpt-5-mini",
            deep_thinker="gpt-5",
            output_language="English",
        )

    def test_runner_executes_graph_and_persists_runtime_artifacts(self):
        snapshots = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_patch = {"results_dir": tmp_dir}
            with patch.dict("tradingagents.runtime.runner.DEFAULT_CONFIG", config_patch, clear=False):
                runner = TradingAgentsRuntimeRunner(graph_factory=FakeTradingGraph)
                result = runner.run(
                    self.request,
                    session_id="run-123",
                    hooks=RuntimeRunnerHooks(on_snapshot_updated=snapshots.append),
                )

            self.assertEqual(result.decision, "processed:BUY")
            self.assertEqual(result.snapshot.status, RunLifecycleState.COMPLETED)
            self.assertEqual(result.snapshot.session_id, "run-123")
            self.assertIn("Portfolio Manager Decision", result.snapshot.compiled_report)
            self.assertEqual(result.snapshot.export_info.log_path, str(result.artifacts.log_file))
            self.assertTrue(result.artifacts.log_file.exists())
            self.assertTrue((result.artifacts.report_dir / "market_report.md").exists())
            self.assertTrue((result.artifacts.report_dir / "investment_plan.md").exists())
            self.assertTrue((result.artifacts.report_dir / "final_trade_decision.md").exists())
            self.assertIn("Selected ticker: SPY", result.artifacts.log_file.read_text(encoding="utf-8"))
            self.assertIn("get_stock_data", result.artifacts.log_file.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(snapshots), 3)
            self.assertEqual(snapshots[-1].status, RunLifecycleState.COMPLETED)

    def test_runner_normalizes_failures_into_runtime_error_with_failed_snapshot(self):
        failed = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            config_patch = {"results_dir": tmp_dir}
            with patch.dict("tradingagents.runtime.runner.DEFAULT_CONFIG", config_patch, clear=False):
                runner = TradingAgentsRuntimeRunner(graph_factory=FailingTradingGraph)
                with self.assertRaises(RuntimeRunnerError) as ctx:
                    runner.run(
                        self.request,
                        hooks=RuntimeRunnerHooks(
                            on_run_failed=lambda error, snapshot: failed.append((error, snapshot))
                        ),
                    )

        error = ctx.exception.run_error
        snapshot = ctx.exception.snapshot
        self.assertEqual(error.code, "runtime_error")
        self.assertIn("stream failed", error.message)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.status, RunLifecycleState.FAILED)
        self.assertTrue(failed)
        self.assertEqual(failed[0][0].code, "runtime_error")


if __name__ == "__main__":
    unittest.main()
