import unittest

from tradingagents.app.backend import build_graph_config
from tradingagents.app.models import AnalysisRequest


class GraphBackendConfigTests(unittest.TestCase):
    def test_build_graph_config_maps_request_fields_to_runtime_config(self):
        request = AnalysisRequest(
            ticker="SPY",
            analysis_date="2026-03-31",
            analysts=["news", "market"],
            research_depth=5,
            llm_provider="openai",
            backend_url="https://api.openai.com/v1",
            shallow_thinker="gpt-5.4-mini",
            deep_thinker="gpt-5.4",
            openai_reasoning_effort="high",
            output_language="German",
        )

        config = build_graph_config(request)

        self.assertEqual(config["llm_provider"], "openai")
        self.assertEqual(config["backend_url"], "https://api.openai.com/v1")
        self.assertEqual(config["quick_think_llm"], "gpt-5.4-mini")
        self.assertEqual(config["deep_think_llm"], "gpt-5.4")
        self.assertEqual(config["max_debate_rounds"], 5)
        self.assertEqual(config["max_risk_discuss_rounds"], 5)
        self.assertEqual(config["openai_reasoning_effort"], "high")
        self.assertEqual(config["output_language"], "German")


if __name__ == "__main__":
    unittest.main()
