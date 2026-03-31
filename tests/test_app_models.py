import unittest

from tradingagents.app.models import AnalysisRequest


class AnalysisRequestTests(unittest.TestCase):
    def test_request_normalizes_ticker_provider_and_analyst_order(self):
        request = AnalysisRequest(
            ticker=" spy ",
            analysis_date="2026-03-31",
            analysts=["news", "market"],
            research_depth=3,
            llm_provider="OpenAI",
            backend_url="https://api.openai.com/v1",
            shallow_thinker="gpt-5.4-mini",
            deep_thinker="gpt-5.4",
            openai_reasoning_effort="high",
            output_language="German",
        )

        self.assertEqual(request.ticker, "SPY")
        self.assertEqual(request.llm_provider, "openai")
        self.assertEqual(request.analysts, ["market", "news"])

    def test_request_serializes_optional_provider_settings(self):
        request = AnalysisRequest(
            ticker="NVDA",
            analysis_date="2026-04-01",
            analysts=["market", "social", "news", "fundamentals"],
            research_depth=1,
            llm_provider="google",
            backend_url="https://generativelanguage.googleapis.com/v1",
            shallow_thinker="gemini-2.5-flash",
            deep_thinker="gemini-3.1-pro-preview",
            google_thinking_level="high",
            output_language="English",
        )

        self.assertEqual(
            request.to_dict(),
            {
                "ticker": "NVDA",
                "analysis_date": "2026-04-01",
                "analysts": ["market", "social", "news", "fundamentals"],
                "research_depth": 1,
                "llm_provider": "google",
                "backend_url": "https://generativelanguage.googleapis.com/v1",
                "shallow_thinker": "gemini-2.5-flash",
                "deep_thinker": "gemini-3.1-pro-preview",
                "google_thinking_level": "high",
                "openai_reasoning_effort": None,
                "anthropic_effort": None,
                "output_language": "English",
            },
        )


if __name__ == "__main__":
    unittest.main()
