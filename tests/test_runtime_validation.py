import unittest
from datetime import date

from cli.models import AnalystType
from tradingagents.runtime.options import DEFAULT_BACKEND_URL, DEFAULT_DEEP_MODEL, DEFAULT_QUICK_MODEL
from tradingagents.runtime.schemas import AnalystKey, ProviderName
from tradingagents.runtime.validation import (
    RunRequestValidationError,
    normalize_analysis_date,
    normalize_output_language,
    normalize_ticker_symbol,
    validate_run_request,
)


class RuntimeValidationTests(unittest.TestCase):
    def test_normalize_ticker_symbol_rejects_blank_and_uppercases(self):
        self.assertEqual(normalize_ticker_symbol(" spy "), "SPY")

        with self.assertRaises(RunRequestValidationError) as ctx:
            normalize_ticker_symbol("   ")

        self.assertEqual(ctx.exception.issues[0].field, "ticker")

    def test_normalize_analysis_date_rejects_future_dates(self):
        self.assertEqual(
            normalize_analysis_date("2026-03-31", today=date(2026, 4, 1)),
            "2026-03-31",
        )

        with self.assertRaises(RunRequestValidationError) as ctx:
            normalize_analysis_date("2026-04-02", today=date(2026, 4, 1))

        self.assertEqual(ctx.exception.issues[0].field, "analysis_date")

    def test_validate_run_request_normalizes_cli_payload(self):
        request = validate_run_request(
            {
                "ticker": " spy ",
                "analysis_date": "2026-03-31",
                "analysts": [AnalystType.MARKET, AnalystType.NEWS],
                "research_depth": 3,
                "llm_provider": "openai",
                "backend_url": "",
                "shallow_thinker": DEFAULT_QUICK_MODEL,
                "deep_thinker": DEFAULT_DEEP_MODEL,
                "output_language": " Turkish ",
            }
        )

        self.assertEqual(request.ticker, "SPY")
        self.assertEqual(request.analysis_date, "2026-03-31")
        self.assertEqual(request.llm_provider, ProviderName.OPENAI)
        self.assertEqual(request.backend_url, DEFAULT_BACKEND_URL)
        self.assertEqual(request.analysts, [AnalystKey.MARKET, AnalystKey.NEWS])
        self.assertEqual(request.output_language, "Turkish")

    def test_validate_run_request_rejects_provider_specific_fields_for_other_providers(self):
        with self.assertRaises(RunRequestValidationError) as ctx:
            validate_run_request(
                {
                    "ticker": "SPY",
                    "analysis_date": "2026-03-31",
                    "analysts": [AnalystType.MARKET],
                    "research_depth": 1,
                    "llm_provider": "google",
                    "backend_url": "",
                    "shallow_thinker": "gemini-3-flash-preview",
                    "deep_thinker": "gemini-3.1-pro-preview",
                    "openai_reasoning_effort": "high",
                    "output_language": "English",
                }
            )

        self.assertEqual(ctx.exception.issues[0].field, "openai_reasoning_effort")

    def test_validate_run_request_rejects_unsupported_research_depth_and_models(self):
        with self.assertRaises(RunRequestValidationError) as ctx:
            validate_run_request(
                {
                    "ticker": "SPY",
                    "analysis_date": "2026-03-31",
                    "analysts": [AnalystType.MARKET],
                    "research_depth": 2,
                    "llm_provider": "openai",
                    "backend_url": DEFAULT_BACKEND_URL,
                    "shallow_thinker": "not-a-real-openai-model",
                    "deep_thinker": DEFAULT_DEEP_MODEL,
                    "output_language": "English",
                }
            )

        fields = {issue.field for issue in ctx.exception.issues}
        self.assertIn("research_depth", fields)
        self.assertIn("shallow_thinker", fields)

    def test_output_language_must_be_present(self):
        with self.assertRaises(RunRequestValidationError) as ctx:
            normalize_output_language("   ")

        self.assertEqual(ctx.exception.issues[0].field, "output_language")


if __name__ == "__main__":
    unittest.main()
