import tempfile
import threading
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from tradingagents.runtime.options import (
    DEFAULT_BACKEND_URL,
    DEFAULT_DEEP_MODEL,
    DEFAULT_QUICK_MODEL,
)
from tradingagents.runtime.runner import (
    RunResult,
    RuntimeRunnerCanceled,
    RuntimeRunnerHooks,
    RuntimeRunArtifacts,
)
from tradingagents.runtime.schemas import (
    AgentStatusSnapshot,
    ExportInfo,
    ProviderName,
    RunError,
    RunLifecycleState,
    RunRequest,
    SessionMessage,
    SessionSnapshot,
    StatsSnapshot,
)
from tradingagents.runtime.session_state import RuntimeSessionState
from tradingagents.web.app import create_app
from tradingagents.web.api import TradingAgentsWebService, selected_inputs_from_request


def make_run_request() -> RunRequest:
    return RunRequest(
        ticker="SPY",
        analysis_date="2026-03-31",
        analysts=["market"],
        research_depth=1,
        llm_provider=ProviderName.OPENAI,
        backend_url=DEFAULT_BACKEND_URL,
        shallow_thinker=DEFAULT_QUICK_MODEL,
        deep_thinker=DEFAULT_DEEP_MODEL,
        output_language="English",
    )


def make_request_payload():
    return {
        "ticker": "SPY",
        "analysis_date": "2026-03-31",
        "analysts": ["market"],
        "research_depth": 1,
        "llm_provider": "openai",
        "backend_url": DEFAULT_BACKEND_URL,
        "shallow_thinker": DEFAULT_QUICK_MODEL,
        "deep_thinker": DEFAULT_DEEP_MODEL,
        "output_language": "English",
    }


class SuccessfulWebRunner:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    def run(self, run_request, *, session_id=None, hooks=None):
        hooks = hooks or RuntimeRunnerHooks()
        artifacts = self._artifacts(run_request)

        running_snapshot = SessionSnapshot(
            session_id=session_id,
            request=run_request,
            selected_inputs=selected_inputs_from_request(run_request),
            status=RunLifecycleState.RUNNING,
            agent_statuses=[
                AgentStatusSnapshot(name="Market Analyst", status="in_progress")
            ],
            messages=[SessionMessage(timestamp="12:00:00", content="Started analysis")],
            report_sections={"market_report": None, "investment_plan": None},
            stats=StatsSnapshot(llm_calls=1, tool_calls=1, total_tokens=10),
            export_info=ExportInfo(log_path=str(artifacts.log_file)),
        )
        hooks.on_snapshot_updated and hooks.on_snapshot_updated(running_snapshot)

        final_state = {
            "market_report": "Market report",
            "investment_debate_state": {
                "bull_history": "Bull case",
                "bear_history": "Bear case",
                "judge_decision": "Research decision",
            },
            "trader_investment_plan": "Trader plan",
            "risk_debate_state": {
                "aggressive_history": "Aggressive risk",
                "conservative_history": "Conservative risk",
                "neutral_history": "Neutral risk",
                "judge_decision": "Portfolio decision",
            },
            "final_trade_decision": "BUY",
        }
        completed_snapshot = SessionSnapshot(
            session_id=session_id,
            request=run_request,
            selected_inputs=selected_inputs_from_request(run_request),
            status=RunLifecycleState.COMPLETED,
            agent_statuses=[
                AgentStatusSnapshot(name="Market Analyst", status="completed"),
                AgentStatusSnapshot(name="Research Manager", status="completed"),
                AgentStatusSnapshot(name="Trader", status="completed"),
                AgentStatusSnapshot(name="Portfolio Manager", status="completed"),
            ],
            messages=[
                SessionMessage(timestamp="12:00:00", content="Started analysis"),
                SessionMessage(timestamp="12:00:01", content="Completed analysis"),
            ],
            current_report="### Market Analysis\nMarket report",
            report_sections={
                "market_report": "Market report",
                "investment_plan": "Research decision",
                "trader_investment_plan": "Trader plan",
                "final_trade_decision": "Portfolio decision",
            },
            compiled_report="## Portfolio Management Decision\n\n### Portfolio Manager Decision\nPortfolio decision",
            structured_report_sections={"final_trade_decision": "Portfolio decision"},
            stats=StatsSnapshot(llm_calls=2, tool_calls=1, total_tokens=42),
            export_info=ExportInfo(log_path=str(artifacts.log_file)),
        )
        hooks.on_snapshot_updated and hooks.on_snapshot_updated(completed_snapshot)

        result = RunResult(
            session_id=session_id,
            request=run_request,
            final_state=final_state,
            decision="processed:BUY",
            snapshot=completed_snapshot,
            session_state=RuntimeSessionState(),
            artifacts=artifacts,
        )
        hooks.on_run_completed and hooks.on_run_completed(result)
        return result

    def _artifacts(self, run_request):
        results_dir = self.base_dir / run_request.ticker / run_request.analysis_date
        report_dir = results_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        log_file = results_dir / "message_tool.log"
        log_file.write_text("log line\n", encoding="utf-8")
        return RuntimeRunArtifacts(
            results_dir=results_dir,
            report_dir=report_dir,
            log_file=log_file,
        )


class BlockingWebRunner(SuccessfulWebRunner):
    def __init__(self, base_dir: str, started_event: threading.Event, release_event: threading.Event):
        super().__init__(base_dir)
        self.started_event = started_event
        self.release_event = release_event

    def run(self, run_request, *, session_id=None, hooks=None):
        hooks = hooks or RuntimeRunnerHooks()
        artifacts = self._artifacts(run_request)
        running_snapshot = SessionSnapshot(
            session_id=session_id,
            request=run_request,
            selected_inputs=selected_inputs_from_request(run_request),
            status=RunLifecycleState.RUNNING,
            agent_statuses=[
                AgentStatusSnapshot(name="Market Analyst", status="in_progress")
            ],
            report_sections={"market_report": None},
            stats=StatsSnapshot(),
            export_info=ExportInfo(log_path=str(artifacts.log_file)),
        )
        hooks.on_snapshot_updated and hooks.on_snapshot_updated(running_snapshot)
        self.started_event.set()
        self.release_event.wait(timeout=5)
        return super().run(run_request, session_id=session_id, hooks=hooks)


class StoppableWebRunner(SuccessfulWebRunner):
    def __init__(
        self,
        base_dir: str,
        stop_observed_event: threading.Event | None = None,
        release_after_stop_event: threading.Event | None = None,
    ):
        super().__init__(base_dir)
        self.stop_observed_event = stop_observed_event
        self.release_after_stop_event = release_after_stop_event

    def run(self, run_request, *, session_id=None, hooks=None):
        hooks = hooks or RuntimeRunnerHooks()
        artifacts = self._artifacts(run_request)
        running_snapshot = SessionSnapshot(
            session_id=session_id,
            request=run_request,
            selected_inputs=selected_inputs_from_request(run_request),
            status=RunLifecycleState.RUNNING,
            agent_statuses=[
                AgentStatusSnapshot(name="Market Analyst", status="in_progress")
            ],
            messages=[SessionMessage(timestamp="12:00:00", content="Started analysis")],
            report_sections={"market_report": None},
            stats=StatsSnapshot(),
            export_info=ExportInfo(log_path=str(artifacts.log_file)),
        )
        hooks.on_snapshot_updated and hooks.on_snapshot_updated(running_snapshot)

        for _ in range(50):
            if hooks.should_stop and hooks.should_stop():
                if self.stop_observed_event is not None:
                    self.stop_observed_event.set()
                if self.release_after_stop_event is not None:
                    self.release_after_stop_event.wait(timeout=5)
                canceled_snapshot = SessionSnapshot(
                    session_id=session_id,
                    request=run_request,
                    selected_inputs=selected_inputs_from_request(run_request),
                    status=RunLifecycleState.CANCELED,
                    agent_statuses=[
                        AgentStatusSnapshot(name="Market Analyst", status="in_progress")
                    ],
                    messages=[
                        SessionMessage(timestamp="12:00:00", content="Started analysis"),
                        SessionMessage(
                            timestamp="12:00:01",
                            content="Run canceled by user request.",
                        ),
                    ],
                    report_sections={"market_report": None},
                    stats=StatsSnapshot(),
                    export_info=ExportInfo(log_path=str(artifacts.log_file)),
                    errors=[],
                )
                hooks.on_snapshot_updated and hooks.on_snapshot_updated(canceled_snapshot)
                run_error = RunError(
                    message="Run canceled by user request.",
                    code="canceled",
                )
                hooks.on_run_canceled and hooks.on_run_canceled(
                    run_error,
                    canceled_snapshot,
                )
                raise RuntimeRunnerCanceled(run_error, canceled_snapshot)
            time.sleep(0.01)

        return super().run(run_request, session_id=session_id, hooks=hooks)


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        runner_factory = lambda: SuccessfulWebRunner(self.tmp_dir.name)
        service = TradingAgentsWebService(runner_factory=runner_factory)
        self.client = TestClient(create_app(service=service))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _wait_for_completion(self, session_id: str):
        for _ in range(50):
            response = self.client.get(f"/api/runs/{session_id}")
            payload = response.json()
            if payload["status"] == "completed":
                return payload
            time.sleep(0.01)
        self.fail(f"Run {session_id} did not complete in time")

    def test_options_health_and_index_routes(self):
        health = self.client.get("/health")
        options = self.client.get("/api/options")
        index = self.client.get("/")
        script = self.client.get("/static/app.js")
        stylesheet = self.client.get("/static/styles.css")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(options.status_code, 200)
        self.assertIn("providers", options.json())
        self.assertIn("defaults", options.json())
        self.assertEqual(index.status_code, 200)
        self.assertIn("TradingAgents Web UI", index.text)
        self.assertIn('class="workspace-header"', index.text)
        self.assertIn('id="setup-form"', index.text)
        self.assertIn('id="agent-status-groups"', index.text)
        self.assertIn('id="compiled-report"', index.text)
        self.assertIn('id="run-status-detail"', index.text)
        self.assertIn('class="setup-grid"', index.text)
        self.assertIn('class="activity-grid"', index.text)
        self.assertIn('class="results-grid"', index.text)
        self.assertIn("TradingAgents Dashboard", index.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("ACTIVE_RUN_STATES", script.text)
        self.assertIn('"stopping"', script.text)
        self.assertIn("syncFormWithSnapshot", script.text)
        self.assertIn("selected_inputs", script.text)
        self.assertIn(
            "Waiting for the current LLM or tool call to finish before the run can cancel.",
            script.text,
        )
        self.assertEqual(stylesheet.status_code, 200)
        self.assertIn(".dashboard-grid", stylesheet.text)
        self.assertIn(".workspace-header", stylesheet.text)
        self.assertIn(".setup-grid", stylesheet.text)
        self.assertIn(".activity-grid", stylesheet.text)
        self.assertIn(".results-grid", stylesheet.text)
        self.assertIn(".summary-detail", stylesheet.text)

    def test_create_run_rejects_invalid_payload(self):
        payload = make_request_payload()
        payload["ticker"] = " "

        response = self.client.post("/api/runs", json=payload)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["issues"][0]["field"], "ticker")

    def test_active_run_endpoint_returns_404_when_no_run_is_active(self):
        response = self.client.get("/api/runs/active")

        self.assertEqual(response.status_code, 404)
        self.assertIn("No active run", response.json()["detail"]["message"])

    def test_run_creation_snapshot_retrieval_events_and_export(self):
        create_response = self.client.post("/api/runs", json=make_request_payload())
        self.assertEqual(create_response.status_code, 201)

        session_id = create_response.json()["session_id"]
        snapshot = self._wait_for_completion(session_id)

        self.assertEqual(snapshot["status"], "completed")
        self.assertIn("compiled_report", snapshot)
        self.assertEqual(snapshot["selected_inputs"]["ticker"], "SPY")

        event_response = self.client.get(f"/api/runs/{session_id}/events")
        self.assertEqual(event_response.status_code, 200)
        self.assertEqual(event_response.headers["content-type"], "text/event-stream; charset=utf-8")
        self.assertIn("event: snapshot", event_response.text)
        self.assertIn('"status": "completed"', event_response.text)

        export_response = self.client.post(f"/api/runs/{session_id}/export")
        self.assertEqual(export_response.status_code, 200)
        report_path = Path(export_response.json()["report_path"])
        self.assertTrue(report_path.exists())

        refreshed_snapshot = self.client.get(f"/api/runs/{session_id}").json()
        self.assertEqual(refreshed_snapshot["export_info"]["report_path"], str(report_path))

    def test_single_active_run_guard_blocks_second_request(self):
        started = threading.Event()
        release = threading.Event()
        blocking_service = TradingAgentsWebService(
            runner_factory=lambda: BlockingWebRunner(self.tmp_dir.name, started, release)
        )
        client = TestClient(create_app(service=blocking_service))

        first = client.post("/api/runs", json=make_request_payload())
        self.assertEqual(first.status_code, 201)
        self.assertTrue(started.wait(timeout=1))

        active = client.get("/api/runs/active")
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.json()["session_id"], first.json()["session_id"])
        self.assertEqual(active.json()["status"], "running")

        second = client.post("/api/runs", json=make_request_payload())
        self.assertEqual(second.status_code, 409)
        self.assertIn("Only one active run", second.json()["detail"]["message"])

        release.set()
        session_id = first.json()["session_id"]
        for _ in range(50):
            snapshot = client.get(f"/api/runs/{session_id}").json()
            if snapshot["status"] == "completed":
                break
            time.sleep(0.01)
        else:
            self.fail("Blocking run did not finish after release")

    def test_stop_endpoint_cancels_active_run(self):
        stop_observed = threading.Event()
        release_after_stop = threading.Event()
        stoppable_service = TradingAgentsWebService(
            runner_factory=lambda: StoppableWebRunner(
                self.tmp_dir.name,
                stop_observed_event=stop_observed,
                release_after_stop_event=release_after_stop,
            )
        )
        client = TestClient(create_app(service=stoppable_service))

        create_response = client.post("/api/runs", json=make_request_payload())
        self.assertEqual(create_response.status_code, 201)
        session_id = create_response.json()["session_id"]

        stop_response = client.post(f"/api/runs/{session_id}/stop")
        self.assertEqual(stop_response.status_code, 200)
        self.assertEqual(stop_response.json()["status"], "stopping")
        self.assertIn(
            "Stop requested by user",
            stop_response.json()["messages"][-1]["content"],
        )

        stopping_snapshot = client.get(f"/api/runs/{session_id}").json()
        self.assertEqual(stopping_snapshot["status"], "stopping")

        active_response = client.get("/api/runs/active")
        self.assertEqual(active_response.status_code, 200)
        self.assertEqual(active_response.json()["status"], "stopping")

        second = client.post("/api/runs", json=make_request_payload())
        self.assertEqual(second.status_code, 409)
        self.assertIn("Only one active run", second.json()["detail"]["message"])

        self.assertTrue(stop_observed.wait(timeout=1))
        release_after_stop.set()

        for _ in range(50):
            snapshot = client.get(f"/api/runs/{session_id}").json()
            if snapshot["status"] == "canceled":
                break
            time.sleep(0.02)
        else:
            self.fail("Run did not transition to canceled")

        self.assertEqual(snapshot["status"], "canceled")

        active_response = client.get("/api/runs/active")
        self.assertEqual(active_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
