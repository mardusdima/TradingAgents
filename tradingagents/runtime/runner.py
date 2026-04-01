from __future__ import annotations

import copy
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.runtime.schemas import (
    ExportInfo,
    RunError,
    RunLifecycleState,
    RunRequest,
    SessionMessage,
    SessionSnapshot,
    ToolCallSnapshot,
)
from tradingagents.runtime.session_state import RuntimeSessionState
from tradingagents.runtime.stats import StatsCallbackHandler
from tradingagents.runtime.validation import RunRequestValidationError

GraphFactory = Callable[..., Any]
SessionStateFactory = Callable[[], RuntimeSessionState]
StatsHandlerFactory = Callable[[], StatsCallbackHandler]
SnapshotHook = Callable[[SessionSnapshot], None]
MessageHook = Callable[[SessionMessage], None]
ToolCallHook = Callable[[ToolCallSnapshot], None]
RunCompletedHook = Callable[["RunResult"], None]
RunFailedHook = Callable[[RunError, Optional[SessionSnapshot]], None]


@dataclass(frozen=True)
class RuntimeRunArtifacts:
    results_dir: Path
    report_dir: Path
    log_file: Path


@dataclass
class RuntimeRunnerHooks:
    on_snapshot_updated: Optional[SnapshotHook] = None
    on_message_appended: Optional[MessageHook] = None
    on_tool_call_appended: Optional[ToolCallHook] = None
    on_run_completed: Optional[RunCompletedHook] = None
    on_run_failed: Optional[RunFailedHook] = None


@dataclass
class RunResult:
    session_id: Optional[str]
    request: RunRequest
    final_state: Dict[str, Any]
    decision: str
    snapshot: SessionSnapshot
    session_state: RuntimeSessionState
    artifacts: RuntimeRunArtifacts


class RuntimeRunnerError(RuntimeError):
    def __init__(self, run_error: RunError, snapshot: SessionSnapshot | None = None):
        self.run_error = run_error
        self.snapshot = snapshot
        super().__init__(run_error.message)


class TradingAgentsRuntimeRunner:
    def __init__(
        self,
        *,
        graph_factory: GraphFactory = TradingAgentsGraph,
        session_state_factory: SessionStateFactory = RuntimeSessionState,
        stats_handler_factory: StatsHandlerFactory = StatsCallbackHandler,
    ) -> None:
        self._graph_factory = graph_factory
        self._session_state_factory = session_state_factory
        self._stats_handler_factory = stats_handler_factory

    def run(
        self,
        run_request: RunRequest,
        *,
        session_id: str | None = None,
        hooks: RuntimeRunnerHooks | None = None,
    ) -> RunResult:
        hooks = hooks or RuntimeRunnerHooks()
        session_state = self._session_state_factory()
        stats_handler = self._stats_handler_factory()
        errors: List[RunError] = []
        status = RunLifecycleState.VALIDATING

        try:
            selected_analyst_keys = self._normalize_selected_analysts(run_request)
            session_state.init_for_analysis(selected_analyst_keys)
            artifacts = self._prepare_artifacts(run_request)
            self._decorate_session_state(
                session_state,
                artifacts=artifacts,
                hooks=hooks,
            )

            self._emit_snapshot(
                session_state,
                run_request=run_request,
                session_id=session_id,
                status=status,
                stats_handler=stats_handler,
                artifacts=artifacts,
                errors=errors,
                hook=hooks.on_snapshot_updated,
            )

            graph = self._graph_factory(
                selected_analyst_keys,
                config=self._build_runtime_config(run_request),
                debug=True,
                callbacks=[stats_handler],
            )

            session_state.add_message("System", f"Selected ticker: {run_request.ticker}")
            session_state.add_message("System", f"Analysis date: {run_request.analysis_date}")
            session_state.add_message(
                "System",
                "Selected analysts: "
                + ", ".join(analyst.value for analyst in run_request.analysts),
            )
            session_state.start_run()
            status = RunLifecycleState.RUNNING
            self._emit_snapshot(
                session_state,
                run_request=run_request,
                session_id=session_id,
                status=status,
                stats_handler=stats_handler,
                artifacts=artifacts,
                errors=errors,
                hook=hooks.on_snapshot_updated,
            )

            init_agent_state = graph.propagator.create_initial_state(
                run_request.ticker,
                run_request.analysis_date,
            )
            graph_args = graph.propagator.get_graph_args(callbacks=[stats_handler])

            trace: List[Dict[str, Any]] = []
            for chunk in graph.graph.stream(init_agent_state, **graph_args):
                session_state.process_chunk(chunk)
                trace.append(chunk)
                self._emit_snapshot(
                    session_state,
                    run_request=run_request,
                    session_id=session_id,
                    status=status,
                    stats_handler=stats_handler,
                    artifacts=artifacts,
                    errors=errors,
                    hook=hooks.on_snapshot_updated,
                )

            if not trace:
                raise RuntimeRunnerError(
                    RunError(
                        message="Analysis completed without producing a final state.",
                        code="empty_trace",
                    )
                )

            final_state = trace[-1]
            decision = graph.process_signal(final_state["final_trade_decision"])

            session_state.complete_run()
            session_state.add_message(
                "System",
                f"Completed analysis for {run_request.analysis_date}",
            )
            session_state.apply_final_state(final_state)

            snapshot = self._emit_snapshot(
                session_state,
                run_request=run_request,
                session_id=session_id,
                status=RunLifecycleState.COMPLETED,
                stats_handler=stats_handler,
                artifacts=artifacts,
                errors=errors,
                hook=hooks.on_snapshot_updated,
            )

            result = RunResult(
                session_id=session_id,
                request=run_request,
                final_state=final_state,
                decision=decision,
                snapshot=snapshot,
                session_state=session_state,
                artifacts=artifacts,
            )
            if hooks.on_run_completed:
                hooks.on_run_completed(result)
            return result
        except Exception as exc:
            run_error = self._normalize_error(exc)
            errors.append(run_error)
            try:
                session_state.add_message("System", f"Run failed: {run_error.message}")
            except Exception:
                pass

            snapshot = self._safe_failed_snapshot(
                session_state=session_state,
                run_request=run_request,
                session_id=session_id,
                stats_handler=stats_handler,
                errors=errors,
            )
            if hooks.on_snapshot_updated and snapshot is not None:
                hooks.on_snapshot_updated(snapshot)
            if hooks.on_run_failed:
                hooks.on_run_failed(run_error, snapshot)

            if isinstance(exc, RuntimeRunnerError):
                raise RuntimeRunnerError(run_error, snapshot) from exc
            raise RuntimeRunnerError(run_error, snapshot) from exc

    @staticmethod
    def _normalize_selected_analysts(run_request: RunRequest) -> List[str]:
        selected_set = {analyst.value for analyst in run_request.analysts}
        return [
            analyst_key
            for analyst_key in RuntimeSessionState.ANALYST_ORDER
            if analyst_key in selected_set
        ]

    @staticmethod
    def _build_runtime_config(run_request: RunRequest) -> Dict[str, Any]:
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["max_debate_rounds"] = run_request.research_depth
        config["max_risk_discuss_rounds"] = run_request.research_depth
        config["quick_think_llm"] = run_request.shallow_thinker
        config["deep_think_llm"] = run_request.deep_thinker
        config["backend_url"] = run_request.backend_url
        config["llm_provider"] = run_request.llm_provider.value
        config["google_thinking_level"] = run_request.google_thinking_level
        config["openai_reasoning_effort"] = run_request.openai_reasoning_effort
        config["anthropic_effort"] = run_request.anthropic_effort
        config["output_language"] = run_request.output_language
        return config

    @staticmethod
    def _prepare_artifacts(run_request: RunRequest) -> RuntimeRunArtifacts:
        results_dir = (
            Path(DEFAULT_CONFIG["results_dir"])
            / run_request.ticker
            / run_request.analysis_date
        )
        results_dir.mkdir(parents=True, exist_ok=True)
        report_dir = results_dir / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        log_file = results_dir / "message_tool.log"
        log_file.touch(exist_ok=True)
        return RuntimeRunArtifacts(
            results_dir=results_dir,
            report_dir=report_dir,
            log_file=log_file,
        )

    def _decorate_session_state(
        self,
        session_state: RuntimeSessionState,
        *,
        artifacts: RuntimeRunArtifacts,
        hooks: RuntimeRunnerHooks,
    ) -> None:
        session_state.add_message = self._wrap_add_message(
            session_state,
            artifacts=artifacts,
            hook=hooks.on_message_appended,
        )
        session_state.add_tool_call = self._wrap_add_tool_call(
            session_state,
            artifacts=artifacts,
            hook=hooks.on_tool_call_appended,
        )
        session_state.update_report_section = self._wrap_update_report_section(
            session_state,
            artifacts=artifacts,
        )

    @staticmethod
    def _wrap_add_message(
        session_state: RuntimeSessionState,
        *,
        artifacts: RuntimeRunArtifacts,
        hook: MessageHook | None,
    ):
        func = session_state.add_message

        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            message = session_state.messages[-1]
            content = (message.content or "").replace("\n", " ")
            with artifacts.log_file.open("a", encoding="utf-8") as file_obj:
                file_obj.write(
                    f"{message.timestamp} [{message.message_type}] {content}\n"
                )
            if hook:
                hook(message)

        return wrapper

    @staticmethod
    def _wrap_add_tool_call(
        session_state: RuntimeSessionState,
        *,
        artifacts: RuntimeRunArtifacts,
        hook: ToolCallHook | None,
    ):
        func = session_state.add_tool_call

        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            tool_call = session_state.tool_calls[-1]
            arguments = (
                tool_call.arguments if isinstance(tool_call.arguments, dict) else {}
            )
            args_str = ", ".join(f"{key}={value}" for key, value in arguments.items())
            if not args_str:
                args_str = str(tool_call.arguments)
            with artifacts.log_file.open("a", encoding="utf-8") as file_obj:
                file_obj.write(
                    f"{tool_call.timestamp} [Tool Call] "
                    f"{tool_call.tool_name}({args_str})\n"
                )
            if hook:
                hook(tool_call)

        return wrapper

    @staticmethod
    def _wrap_update_report_section(
        session_state: RuntimeSessionState,
        *,
        artifacts: RuntimeRunArtifacts,
    ):
        func = session_state.update_report_section

        @wraps(func)
        def wrapper(section_name, content, *args, **kwargs):
            func(section_name, content, *args, **kwargs)
            section_content = session_state.report_sections.get(section_name)
            if section_content is None:
                return
            if isinstance(section_content, list):
                text = "\n".join(str(item) for item in section_content)
            else:
                text = str(section_content)
            (artifacts.report_dir / f"{section_name}.md").write_text(
                text,
                encoding="utf-8",
            )

        return wrapper

    @staticmethod
    def _selected_inputs(run_request: RunRequest) -> Dict[str, Any]:
        return {
            "ticker": run_request.ticker,
            "analysis_date": run_request.analysis_date,
            "research_depth": run_request.research_depth,
            "llm_provider": run_request.llm_provider.value,
            "backend_url": run_request.backend_url,
            "shallow_thinker": run_request.shallow_thinker,
            "deep_thinker": run_request.deep_thinker,
            "analysts": [analyst.value for analyst in run_request.analysts],
            "google_thinking_level": run_request.google_thinking_level,
            "openai_reasoning_effort": run_request.openai_reasoning_effort,
            "anthropic_effort": run_request.anthropic_effort,
            "output_language": run_request.output_language,
        }

    def _emit_snapshot(
        self,
        session_state: RuntimeSessionState,
        *,
        run_request: RunRequest,
        session_id: str | None,
        status: RunLifecycleState,
        stats_handler: StatsCallbackHandler,
        artifacts: RuntimeRunArtifacts,
        errors: List[RunError],
        hook: SnapshotHook | None,
    ) -> SessionSnapshot:
        snapshot = session_state.to_snapshot(
            session_id=session_id,
            request=run_request,
            selected_inputs=self._selected_inputs(run_request),
            status=status,
            stats=stats_handler.to_snapshot(),
            export_info=ExportInfo(log_path=str(artifacts.log_file)),
            errors=list(errors),
        )
        if hook:
            hook(snapshot)
        return snapshot

    def _safe_failed_snapshot(
        self,
        *,
        session_state: RuntimeSessionState,
        run_request: RunRequest,
        session_id: str | None,
        stats_handler: StatsCallbackHandler,
        errors: List[RunError],
    ) -> SessionSnapshot | None:
        try:
            artifacts = self._prepare_artifacts(run_request)
            return session_state.to_snapshot(
                session_id=session_id,
                request=run_request,
                selected_inputs=self._selected_inputs(run_request),
                status=RunLifecycleState.FAILED,
                stats=stats_handler.to_snapshot(),
                export_info=ExportInfo(log_path=str(artifacts.log_file)),
                errors=list(errors),
            )
        except Exception:
            return None

    @staticmethod
    def _normalize_error(exc: Exception) -> RunError:
        if isinstance(exc, RuntimeRunnerError):
            return exc.run_error
        if isinstance(exc, RunRequestValidationError):
            return RunError(
                message=str(exc),
                code="validation_error",
                details={
                    "issues": [
                        {"field": issue.field, "message": issue.message}
                        for issue in exc.issues
                    ]
                },
            )
        return RunError(
            message=str(exc) or "Analysis run failed unexpectedly.",
            code="runtime_error",
        )
