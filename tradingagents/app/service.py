from __future__ import annotations

import re
import threading
from typing import Callable, Optional

from .history import AnalysisHistoryRepository
from .models import AnalysisRequest, RunDetail, RunSummary


SECTION_KEYS = {
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
}


class AnalysisRunService:
    """Shared executor that translates streamed backend output into canonical history."""

    def __init__(
        self,
        repository: AnalysisHistoryRepository,
        *,
        backend_factory: Callable[[AnalysisRequest], object],
    ):
        self.repository = repository
        self.backend_factory = backend_factory

    def create_pending_run(self, request: AnalysisRequest, *, source: str) -> RunSummary:
        created = self.repository.create_run(request, source=source, status="pending")
        self.repository.record_event(
            created.run_id,
            event_type="message",
            message_type="System",
            content=f"Selected ticker: {request.ticker}",
        )
        self.repository.record_event(
            created.run_id,
            event_type="message",
            message_type="System",
            content=f"Analysis date: {request.analysis_date}",
        )
        return created

    def execute_run(
        self,
        run_id: str,
        request: AnalysisRequest,
        *,
        on_chunk: Optional[Callable[[dict], None]] = None,
    ) -> RunDetail:
        backend = self.backend_factory(request)
        self.repository.mark_running(run_id)

        try:
            for chunk in backend.stream(request):
                if on_chunk is not None:
                    on_chunk(chunk)
                self._apply_chunk(run_id, chunk)
                self._sync_stats(run_id, backend)
            rating = self._extract_rating(
                self.repository.get_run_detail(run_id).sections.get("final_trade_decision", "")
            )
            self._sync_stats(run_id, backend)
            self.repository.mark_completed(run_id, rating=rating)
        except Exception as exc:  # pragma: no cover - covered via tests
            self._sync_stats(run_id, backend)
            self.repository.mark_failed(run_id, error_message=str(exc))

        return self.repository.get_run_detail(run_id)

    def run_sync(self, request: AnalysisRequest, *, source: str) -> RunDetail:
        created = self.create_pending_run(request, source=source)
        return self.execute_run(created.run_id, request)

    def _apply_chunk(self, run_id: str, chunk: dict) -> None:
        for key in SECTION_KEYS:
            if key in chunk and chunk[key]:
                self.repository.upsert_section(run_id, section_key=key, content=str(chunk[key]))

        if chunk.get("investment_debate_state"):
            formatted = self._format_investment_plan(chunk["investment_debate_state"])
            if formatted:
                self.repository.upsert_section(run_id, section_key="investment_plan", content=formatted)

        if chunk.get("risk_debate_state"):
            formatted = self._format_risk_decision(chunk["risk_debate_state"])
            if formatted:
                self.repository.upsert_section(run_id, section_key="final_trade_decision", content=formatted)

        messages = chunk.get("messages") or []
        for message in messages:
            text = self._message_content(message)
            if text:
                self.repository.record_event(
                    run_id,
                    event_type="message",
                    message_type="Agent",
                    content=text,
                )

    def _format_investment_plan(self, debate_state: dict) -> Optional[str]:
        if debate_state.get("judge_decision"):
            return f"### Research Manager Decision\n{debate_state['judge_decision']}"

        parts = []
        if debate_state.get("bull_history"):
            parts.append(f"### Bull Researcher Analysis\n{debate_state['bull_history']}")
        if debate_state.get("bear_history"):
            parts.append(f"### Bear Researcher Analysis\n{debate_state['bear_history']}")
        return "\n\n".join(parts) if parts else None

    def _format_risk_decision(self, risk_state: dict) -> Optional[str]:
        if risk_state.get("judge_decision"):
            return f"### Portfolio Manager Decision\n{risk_state['judge_decision']}"

        parts = []
        if risk_state.get("aggressive_history"):
            parts.append(f"### Aggressive Analyst Analysis\n{risk_state['aggressive_history']}")
        if risk_state.get("conservative_history"):
            parts.append(f"### Conservative Analyst Analysis\n{risk_state['conservative_history']}")
        if risk_state.get("neutral_history"):
            parts.append(f"### Neutral Analyst Analysis\n{risk_state['neutral_history']}")
        return "\n\n".join(parts) if parts else None

    def _message_content(self, message) -> Optional[str]:
        if isinstance(message, str):
            return message.strip() or None
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip() or None
        return None

    def _extract_rating(self, content: str) -> Optional[str]:
        if not content:
            return None

        for pattern in (
            r"\*\*Rating\*\*:\s*([A-Z]+)",
            r"FINAL TRANSACTION PROPOSAL:\s*\*\*([A-Z]+)\*\*",
        ):
            match = re.search(pattern, content, flags=re.IGNORECASE)
            if match:
                return match.group(1).upper()
        return None

    def _sync_stats(self, run_id: str, backend: object) -> None:
        get_stats = getattr(backend, "get_stats", None)
        if callable(get_stats):
            stats = get_stats()
            if stats is not None:
                self.repository.update_stats(run_id, stats)


class SingleRunCoordinator:
    """Starts background runs while enforcing a single active analysis."""

    def __init__(self, service: AnalysisRunService):
        self.service = service
        self._lock = threading.Lock()
        self.active_run_id: Optional[str] = None
        self._threads: dict[str, threading.Thread] = {}

    def start(self, request: AnalysisRequest, *, source: str) -> str:
        with self._lock:
            if self.active_run_id is not None:
                raise RuntimeError("An analysis is already running.")
            created = self.service.create_pending_run(request, source=source)
            self.active_run_id = created.run_id

        thread = threading.Thread(
            target=self._execute_in_thread,
            args=(created.run_id, request),
            daemon=True,
        )
        self._threads[created.run_id] = thread
        thread.start()
        return created.run_id

    def _execute_in_thread(self, run_id: str, request: AnalysisRequest) -> None:
        try:
            self.service.execute_run(run_id, request)
        finally:
            with self._lock:
                if self.active_run_id == run_id:
                    self.active_run_id = None
                self._threads.pop(run_id, None)
