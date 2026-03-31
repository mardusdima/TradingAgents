import tempfile
import unittest
from pathlib import Path

from tradingagents.app.history import AnalysisHistoryRepository
from tradingagents.app.importer import LegacyAnalysisImporter


class LegacyAnalysisImporterTests(unittest.TestCase):
    def test_importer_backfills_results_and_reports_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy_results = root / "results" / "SPY" / "2026-03-31" / "reports"
            legacy_results.mkdir(parents=True)
            (legacy_results / "market_report.md").write_text("Imported market report")
            (legacy_results.parent / "message_tool.log").write_text(
                "16:27:40 [System] Completed analysis for 2026-03-31\n"
            )

            legacy_report = root / "reports" / "SPY_20260331_162753"
            legacy_report.mkdir(parents=True)
            (legacy_report / "complete_report.md").write_text(
                "# Trading Analysis Report: SPY\n\nImported complete report"
            )

            repository = AnalysisHistoryRepository(root / "results")
            importer = LegacyAnalysisImporter(root, repository)

            first_import_count = importer.import_existing()
            second_import_count = importer.import_existing()
            imported_runs = repository.list_runs(status="completed")

            self.assertEqual(first_import_count, 2)
            self.assertEqual(second_import_count, 0)
            self.assertEqual(len(imported_runs), 2)
            self.assertTrue(all(run.source == "legacy" for run in imported_runs))


if __name__ == "__main__":
    unittest.main()
