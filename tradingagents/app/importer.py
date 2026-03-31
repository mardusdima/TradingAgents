from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from .history import AnalysisHistoryRepository
from .models import AnalysisRequest


LEGACY_SECTION_MAP = {
    "market_report.md": "market_report",
    "sentiment_report.md": "sentiment_report",
    "news_report.md": "news_report",
    "fundamentals_report.md": "fundamentals_report",
    "investment_plan.md": "investment_plan",
    "trader_investment_plan.md": "trader_investment_plan",
    "final_trade_decision.md": "final_trade_decision",
}


class LegacyAnalysisImporter:
    """Backfills legacy results/ and reports/ artifacts into the canonical store."""

    def __init__(self, project_root: Path | str, repository: AnalysisHistoryRepository):
        self.project_root = Path(project_root)
        self.repository = repository

    def import_existing(self) -> int:
        imported = 0
        imported += self._import_results_runs()
        imported += self._import_saved_reports()
        return imported

    def _import_results_runs(self) -> int:
        legacy_results_root = self.project_root / "results"
        if not legacy_results_root.exists():
            return 0

        imported = 0
        for ticker_dir in sorted(path for path in legacy_results_root.iterdir() if path.is_dir() and path.name != "runs"):
            for dated_dir in sorted(path for path in ticker_dir.iterdir() if path.is_dir()):
                fingerprint = self._fingerprint(dated_dir)
                if self.repository.has_legacy_source(fingerprint):
                    continue

                request = AnalysisRequest(
                    ticker=ticker_dir.name,
                    analysis_date=dated_dir.name,
                    analysts=self._infer_analysts(dated_dir / "reports"),
                    research_depth=1,
                    llm_provider="legacy",
                    backend_url="",
                    shallow_thinker="",
                    deep_thinker="",
                    output_language="English",
                )
                created = self.repository.create_run(
                    request,
                    source="legacy",
                    status="completed",
                    legacy_source_key=fingerprint,
                )

                reports_dir = dated_dir / "reports"
                if reports_dir.exists():
                    for file_name, section_key in LEGACY_SECTION_MAP.items():
                        source_file = reports_dir / file_name
                        if source_file.exists():
                            self.repository.upsert_section(
                                created.run_id,
                                section_key=section_key,
                                content=source_file.read_text(encoding="utf-8"),
                            )

                log_file = dated_dir / "message_tool.log"
                if log_file.exists():
                    content = log_file.read_text(encoding="utf-8")
                    self.repository.write_named_artifact(created.run_id, "message_tool.log", content)
                    self.repository.record_event(
                        created.run_id,
                        event_type="legacy_log",
                        message_type="System",
                        content=content,
                    )

                self.repository.mark_completed(created.run_id)
                imported += 1

        return imported

    def _import_saved_reports(self) -> int:
        legacy_reports_root = self.project_root / "reports"
        if not legacy_reports_root.exists():
            return 0

        imported = 0
        for report_dir in sorted(path for path in legacy_reports_root.iterdir() if path.is_dir()):
            fingerprint = self._fingerprint(report_dir)
            if self.repository.has_legacy_source(fingerprint):
                continue

            ticker, analysis_date = self._parse_saved_report_dir(report_dir.name)
            request = AnalysisRequest(
                ticker=ticker,
                analysis_date=analysis_date,
                analysts=[],
                research_depth=1,
                llm_provider="legacy",
                backend_url="",
                shallow_thinker="",
                deep_thinker="",
                output_language="English",
            )
            created = self.repository.create_run(
                request,
                source="legacy",
                status="completed",
                legacy_source_key=fingerprint,
            )

            complete_report = report_dir / "complete_report.md"
            if complete_report.exists():
                content = complete_report.read_text(encoding="utf-8")
                self.repository.write_named_artifact(created.run_id, "complete_report.md", content)

            self.repository.mark_completed(created.run_id)
            imported += 1

        return imported

    def _fingerprint(self, path: Path) -> str:
        return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()

    def _infer_analysts(self, reports_dir: Path) -> list[str]:
        analysts = []
        if (reports_dir / "market_report.md").exists():
            analysts.append("market")
        if (reports_dir / "sentiment_report.md").exists():
            analysts.append("social")
        if (reports_dir / "news_report.md").exists():
            analysts.append("news")
        if (reports_dir / "fundamentals_report.md").exists():
            analysts.append("fundamentals")
        return analysts

    def _parse_saved_report_dir(self, directory_name: str) -> tuple[str, str]:
        if "_" not in directory_name:
            return directory_name, "1970-01-01"

        ticker, timestamp = directory_name.split("_", 1)
        try:
            dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
            return ticker, dt.strftime("%Y-%m-%d")
        except ValueError:
            return ticker, "1970-01-01"
