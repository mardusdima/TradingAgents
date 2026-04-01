from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from tradingagents.runtime.options import get_runtime_options_catalog
from tradingagents.runtime.reporting import export_report_bundle
from tradingagents.runtime.runner import (
    RunResult,
    RuntimeRunnerError,
    RuntimeRunnerHooks,
    TradingAgentsRuntimeRunner,
)
from tradingagents.runtime.schemas import (
    RunLifecycleState,
    RunRequest,
    SessionSnapshot,
)
from tradingagents.runtime.validation import RunRequestValidationError, validate_run_request

ACTIVE_RUN_STATES = {
    RunLifecycleState.PENDING,
    RunLifecycleState.VALIDATING,
    RunLifecycleState.RUNNING,
}

RunnerFactory = Callable[[], Any]


class ActiveRunConflictError(RuntimeError):
    pass


class SessionNotFoundError(KeyError):
    pass


class ExportUnavailableError(RuntimeError):
    pass


class WebRunSession:
    def __init__(self, session_id: str, request: RunRequest, snapshot: SessionSnapshot):
        self.session_id = session_id
        self.request = request
        self.snapshot = snapshot
        self.result: RunResult | None = None
        self.export_path: Path | None = None
        self.completed = snapshot.status not in ACTIVE_RUN_STATES
        self.events: List[str] = []
        self.condition = threading.Condition()


class WebRunRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: Dict[str, WebRunSession] = {}

    def create_session(self, run_request: RunRequest) -> WebRunSession:
        with self._lock:
            if self.get_active_session() is not None:
                raise ActiveRunConflictError(
                    "Only one active run is supported at a time in the Web UI."
                )

            session_id = str(uuid.uuid4())
            snapshot = SessionSnapshot(
                session_id=session_id,
                request=run_request,
                selected_inputs=selected_inputs_from_request(run_request),
                status=RunLifecycleState.PENDING,
            )
            session = WebRunSession(session_id, run_request, snapshot)
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> WebRunSession:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(session_id)
            return session

    def get_active_session(self) -> WebRunSession | None:
        for session in self._sessions.values():
            if session.snapshot.status in ACTIVE_RUN_STATES:
                return session
        return None


class TradingAgentsWebService:
    def __init__(self, *, runner_factory: RunnerFactory = TradingAgentsRuntimeRunner) -> None:
        self._runner_factory = runner_factory
        self._registry = WebRunRegistry()

    def get_options_payload(self) -> Dict[str, Any]:
        return serialize_for_json(get_runtime_options_catalog())

    def create_run(self, raw_request: Dict[str, Any]) -> SessionSnapshot:
        run_request = validate_run_request(raw_request)
        session = self._registry.create_session(run_request)
        self._publish_snapshot(session, session.snapshot)

        worker = threading.Thread(
            target=self._run_session,
            args=(session,),
            daemon=True,
            name=f"tradingagents-web-run-{session.session_id}",
        )
        worker.start()
        return session.snapshot

    def get_snapshot(self, session_id: str) -> SessionSnapshot:
        return self._registry.get_session(session_id).snapshot

    def stream_events(self, session_id: str) -> Iterator[str]:
        session = self._registry.get_session(session_id)
        cursor = 0

        while True:
            payload: str | None = None
            should_stop = False
            with session.condition:
                while cursor >= len(session.events) and not session.completed:
                    session.condition.wait(timeout=15)
                    if cursor >= len(session.events) and not session.completed:
                        payload = None
                        break

                if cursor < len(session.events):
                    payload = session.events[cursor]
                    cursor += 1
                    should_stop = session.completed and cursor >= len(session.events)
                elif session.completed:
                    break

            if payload is None:
                yield ": keep-alive\n\n"
                continue

            yield f"event: snapshot\ndata: {payload}\n\n"
            if should_stop:
                break

    def export_run_report(self, session_id: str) -> Path:
        session = self._registry.get_session(session_id)
        with session.condition:
            if session.export_path is not None and session.export_path.exists():
                return session.export_path
            if session.result is None:
                raise ExportUnavailableError("Run export is only available after completion.")

            export_dir = session.result.artifacts.results_dir / "web_export"
            report_path = export_report_bundle(
                session.result.final_state,
                session.request.ticker,
                export_dir,
            )
            session.export_path = report_path
            session.snapshot.export_info.report_path = str(report_path)
            self._publish_snapshot(session, session.snapshot)
            return report_path

    def _run_session(self, session: WebRunSession) -> None:
        runner = self._runner_factory()
        hooks = RuntimeRunnerHooks(
            on_snapshot_updated=lambda snapshot: self._publish_snapshot(session, snapshot),
            on_run_completed=lambda result: self._mark_completed(session, result),
            on_run_failed=lambda error, snapshot: self._mark_failed(session, snapshot),
        )

        try:
            result = runner.run(
                session.request,
                session_id=session.session_id,
                hooks=hooks,
            )
        except RuntimeRunnerError:
            with session.condition:
                session.completed = True
                session.condition.notify_all()
            return

        with session.condition:
            session.result = result
            session.completed = True
            session.condition.notify_all()

    def _publish_snapshot(
        self,
        session: WebRunSession,
        snapshot: SessionSnapshot,
    ) -> None:
        serialized = json.dumps(serialize_for_json(snapshot))
        with session.condition:
            session.snapshot = snapshot
            session.events.append(serialized)
            if snapshot.status not in ACTIVE_RUN_STATES:
                session.completed = True
            session.condition.notify_all()

    @staticmethod
    def _mark_completed(session: WebRunSession, result: RunResult) -> None:
        with session.condition:
            session.result = result
            session.completed = True
            session.condition.notify_all()

    @staticmethod
    def _mark_failed(
        session: WebRunSession,
        snapshot: SessionSnapshot | None,
    ) -> None:
        with session.condition:
            if snapshot is not None:
                session.snapshot = snapshot
            session.completed = True
            session.condition.notify_all()


def serialize_for_json(value: Any) -> Any:
    if is_dataclass(value):
        return serialize_for_json(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): serialize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_for_json(item) for item in value]
    return value


def selected_inputs_from_request(run_request: RunRequest) -> Dict[str, Any]:
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


def get_web_service(request: Request) -> TradingAgentsWebService:
    return request.app.state.web_service


def create_api_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/options")
    def get_options(request: Request):
        return get_web_service(request).get_options_payload()

    @router.post("/api/runs", status_code=status.HTTP_201_CREATED)
    def create_run(request: Request, payload: Dict[str, Any]):
        service = get_web_service(request)
        try:
            snapshot = service.create_run(payload)
        except RunRequestValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Run request validation failed.",
                    "issues": [
                        {"field": issue.field, "message": issue.message}
                        for issue in exc.issues
                    ],
                },
            ) from exc
        except ActiveRunConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": str(exc)},
            ) from exc

        return serialize_for_json(snapshot)

    @router.get("/api/runs/{session_id}")
    def get_run_snapshot(session_id: str, request: Request):
        service = get_web_service(request)
        try:
            snapshot = service.get_snapshot(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": f"Run '{session_id}' was not found."},
            ) from exc
        return serialize_for_json(snapshot)

    @router.get("/api/runs/{session_id}/events")
    def get_run_events(session_id: str, request: Request):
        service = get_web_service(request)
        try:
            iterator = service.stream_events(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": f"Run '{session_id}' was not found."},
            ) from exc
        return StreamingResponse(iterator, media_type="text/event-stream")

    @router.post("/api/runs/{session_id}/export")
    def export_run_report(session_id: str, request: Request):
        service = get_web_service(request)
        try:
            report_path = service.export_run_report(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": f"Run '{session_id}' was not found."},
            ) from exc
        except ExportUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": str(exc)},
            ) from exc

        return {"report_path": str(report_path)}

    return router
