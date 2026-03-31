from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import AnalysisRequest, RunDetail, RunEvent, RunStats, RunSummary


SECTION_TITLES = {
    "market_report": "Market Analysis",
    "sentiment_report": "Social Sentiment",
    "news_report": "News Analysis",
    "fundamentals_report": "Fundamentals Analysis",
    "investment_plan": "Research Team Decision",
    "trader_investment_plan": "Trading Team Plan",
    "final_trade_decision": "Portfolio Management Decision",
}

SECTION_ORDER = [
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
    "investment_plan",
    "trader_investment_plan",
    "final_trade_decision",
]


class AnalysisHistoryRepository:
    """SQLite-backed run index with filesystem artifacts per run."""

    def __init__(self, results_dir: Path | str):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.results_dir / "history.db"
        self.runs_dir = self.results_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    analysis_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    rating TEXT,
                    source TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT,
                    legacy_source_key TEXT UNIQUE
                );

                CREATE TABLE IF NOT EXISTS sections (
                    run_id TEXT NOT NULL,
                    section_key TEXT NOT NULL,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, section_key)
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message_type TEXT,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS stats (
                    run_id TEXT PRIMARY KEY,
                    llm_calls INTEGER NOT NULL DEFAULT 0,
                    tool_calls INTEGER NOT NULL DEFAULT 0,
                    tokens_in INTEGER NOT NULL DEFAULT 0,
                    tokens_out INTEGER NOT NULL DEFAULT 0
                );
                """
            )

    def create_run(
        self,
        request: AnalysisRequest,
        *,
        source: str,
        status: str = "pending",
        legacy_source_key: Optional[str] = None,
    ) -> RunSummary:
        run_id = uuid.uuid4().hex
        timestamp = self._timestamp()
        artifact_dir = self._artifact_dir(run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "sections").mkdir(exist_ok=True)
        (artifact_dir / "request.json").write_text(
            json.dumps(request.to_dict(), indent=2),
            encoding="utf-8",
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, ticker, analysis_date, status, rating, source, request_json,
                    created_at, updated_at, error_message, legacy_source_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    request.ticker,
                    request.analysis_date,
                    status,
                    None,
                    source,
                    json.dumps(request.to_dict()),
                    timestamp,
                    timestamp,
                    None,
                    legacy_source_key,
                ),
            )
            connection.execute(
                "INSERT INTO stats (run_id, llm_calls, tool_calls, tokens_in, tokens_out) VALUES (?, 0, 0, 0, 0)",
                (run_id,),
            )

        self._write_summary_json(run_id)
        self._write_complete_report(run_id)
        return self.get_run_summary(run_id)

    def get_run_summary(self, run_id: str) -> RunSummary:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown run_id: {run_id}")
        return self._summary_from_row(row)

    def mark_running(self, run_id: str) -> None:
        self._update_run(run_id, status="running", error_message=None)

    def mark_completed(self, run_id: str, *, rating: Optional[str] = None) -> None:
        self._update_run(run_id, status="completed", rating=rating, error_message=None)
        self._write_summary_json(run_id)
        self._write_complete_report(run_id)

    def mark_failed(self, run_id: str, *, error_message: str) -> None:
        self._update_run(run_id, status="failed", error_message=error_message)
        self._write_summary_json(run_id)
        self._write_complete_report(run_id)

    def record_event(
        self,
        run_id: str,
        *,
        event_type: str,
        message_type: Optional[str],
        content: str,
    ) -> None:
        created_at = self._timestamp()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO events (run_id, event_type, message_type, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, event_type, message_type, content, created_at),
            )
        self._touch_run(run_id)
        self._write_summary_json(run_id)

    def upsert_section(self, run_id: str, *, section_key: str, content: str) -> None:
        updated_at = self._timestamp()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sections (run_id, section_key, content, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id, section_key)
                DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at
                """,
                (run_id, section_key, content, updated_at),
            )
        sections_dir = self._artifact_dir(run_id) / "sections"
        sections_dir.mkdir(parents=True, exist_ok=True)
        (sections_dir / f"{section_key}.md").write_text(content, encoding="utf-8")
        self._touch_run(run_id)
        self._write_summary_json(run_id)
        self._write_complete_report(run_id)

    def update_stats(self, run_id: str, stats: RunStats) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO stats (run_id, llm_calls, tool_calls, tokens_in, tokens_out)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id)
                DO UPDATE SET
                    llm_calls = excluded.llm_calls,
                    tool_calls = excluded.tool_calls,
                    tokens_in = excluded.tokens_in,
                    tokens_out = excluded.tokens_out
                """,
                (
                    run_id,
                    stats.llm_calls,
                    stats.tool_calls,
                    stats.tokens_in,
                    stats.tokens_out,
                ),
            )
        self._touch_run(run_id)
        self._write_summary_json(run_id)

    def write_named_artifact(self, run_id: str, relative_path: str, content: str) -> None:
        artifact_path = self._artifact_dir(run_id) / relative_path
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(content, encoding="utf-8")
        self._touch_run(run_id)
        self._write_summary_json(run_id)

    def list_runs(
        self,
        *,
        ticker: Optional[str] = None,
        status: Optional[str] = None,
        rating: Optional[str] = None,
    ) -> list[RunSummary]:
        query = "SELECT * FROM runs WHERE 1 = 1"
        parameters = []
        if ticker:
            query += " AND ticker = ?"
            parameters.append(ticker.strip().upper())
        if status:
            query += " AND status = ?"
            parameters.append(status)
        if rating:
            query += " AND rating = ?"
            parameters.append(rating)
        query += " ORDER BY created_at DESC, run_id DESC"

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._summary_from_row(row) for row in rows]

    def get_run_detail(self, run_id: str) -> RunDetail:
        summary = self.get_run_summary(run_id)
        with self._connect() as connection:
            sections_rows = connection.execute(
                "SELECT section_key, content FROM sections WHERE run_id = ?",
                (run_id,),
            ).fetchall()
            event_rows = connection.execute(
                "SELECT event_type, message_type, content, created_at FROM events WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
            stats_row = connection.execute(
                "SELECT llm_calls, tool_calls, tokens_in, tokens_out FROM stats WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        sections = {row["section_key"]: row["content"] for row in sections_rows}
        events = [
            RunEvent(
                event_type=row["event_type"],
                message_type=row["message_type"],
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in event_rows
        ]
        stats = RunStats(
            llm_calls=stats_row["llm_calls"] if stats_row else 0,
            tool_calls=stats_row["tool_calls"] if stats_row else 0,
            tokens_in=stats_row["tokens_in"] if stats_row else 0,
            tokens_out=stats_row["tokens_out"] if stats_row else 0,
        )
        return RunDetail(
            summary=summary,
            sections=sections,
            events=events,
            stats=stats,
            artifact_dir=str(self._artifact_dir(run_id)),
        )

    def has_legacy_source(self, legacy_source_key: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM runs WHERE legacy_source_key = ?",
                (legacy_source_key,),
            ).fetchone()
        return row is not None

    def _update_run(self, run_id: str, **fields) -> None:
        timestamp = self._timestamp()
        fields["updated_at"] = timestamp
        assignments = ", ".join(f"{name} = ?" for name in fields.keys())
        parameters = list(fields.values()) + [run_id]
        with self._connect() as connection:
            connection.execute(
                f"UPDATE runs SET {assignments} WHERE run_id = ?",
                parameters,
            )

    def _touch_run(self, run_id: str) -> None:
        self._update_run(run_id)

    def _summary_from_row(self, row: sqlite3.Row) -> RunSummary:
        return RunSummary(
            run_id=row["run_id"],
            ticker=row["ticker"],
            analysis_date=row["analysis_date"],
            status=row["status"],
            rating=row["rating"],
            source=row["source"],
            request=AnalysisRequest(**json.loads(row["request_json"])),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error_message=row["error_message"],
            legacy_source_key=row["legacy_source_key"],
        )

    def _write_summary_json(self, run_id: str) -> None:
        detail = self.get_run_detail(run_id)
        summary_path = self._artifact_dir(run_id) / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "run_id": detail.summary.run_id,
                    "ticker": detail.summary.ticker,
                    "analysis_date": detail.summary.analysis_date,
                    "status": detail.summary.status,
                    "rating": detail.summary.rating,
                    "source": detail.summary.source,
                    "request": detail.summary.request.to_dict(),
                    "stats": {
                        "llm_calls": detail.stats.llm_calls,
                        "tool_calls": detail.stats.tool_calls,
                        "tokens_in": detail.stats.tokens_in,
                        "tokens_out": detail.stats.tokens_out,
                    },
                    "sections": detail.sections,
                    "error_message": detail.summary.error_message,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_complete_report(self, run_id: str) -> None:
        detail = self.get_run_detail(run_id)
        parts = []
        for key in SECTION_ORDER:
            content = detail.sections.get(key)
            if content:
                parts.append(f"## {SECTION_TITLES.get(key, key)}\n\n{content}")

        if detail.summary.error_message:
            parts.append(f"## Error\n\n{detail.summary.error_message}")

        body = "\n\n".join(parts)
        report = (
            f"# Trading Analysis Report: {detail.summary.ticker}\n\n"
            f"Generated: {self._timestamp()}\n\n"
        )
        if body:
            report += body
        (self._artifact_dir(run_id) / "complete_report.md").write_text(
            report,
            encoding="utf-8",
        )

    def _artifact_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
