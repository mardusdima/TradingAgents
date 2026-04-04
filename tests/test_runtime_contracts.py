import unittest

from cli.models import AnalystType
from cli.utils import ANALYST_ORDER
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS
from tradingagents.runtime.options import (
    ANALYST_OPTIONS,
    DEFAULT_BACKEND_URL,
    DEFAULT_DEEP_MODEL,
    DEFAULT_OUTPUT_LANGUAGE,
    DEFAULT_PROVIDER,
    DEFAULT_QUICK_MODEL,
    OUTPUT_LANGUAGE_OPTIONS,
    PROVIDER_OPTIONS,
    RESEARCH_DEPTH_OPTIONS,
    TICKER_INPUT_EXAMPLES,
    get_runtime_options_catalog,
)
from tradingagents.runtime.schemas import (
    AnalystKey,
    EventType,
    ProviderName,
    RunLifecycleState,
    RunRequest,
    SessionMessage,
    SessionSnapshot,
    ToolCallSnapshot,
)


class RuntimeContractsTests(unittest.TestCase):
    def test_runtime_option_catalog_contains_shared_selectables(self):
        catalog = get_runtime_options_catalog()

        self.assertEqual(
            {provider.value.value for provider in catalog.providers},
            set(MODEL_OPTIONS.keys()),
        )
        self.assertEqual(
            [option.value.value for option in catalog.analysts],
            [option.value.value for option in ANALYST_OPTIONS],
        )
        self.assertEqual(
            [option.value for option in catalog.research_depths],
            [option.value for option in RESEARCH_DEPTH_OPTIONS],
        )
        self.assertEqual(
            [option.value for option in catalog.output_languages],
            [option.value for option in OUTPUT_LANGUAGE_OPTIONS],
        )
        self.assertEqual(
            catalog.defaults.llm_provider,
            DEFAULT_PROVIDER,
        )
        self.assertEqual(catalog.defaults.backend_url, DEFAULT_BACKEND_URL)
        self.assertEqual(catalog.defaults.quick_model, DEFAULT_QUICK_MODEL)
        self.assertEqual(catalog.defaults.deep_model, DEFAULT_DEEP_MODEL)
        self.assertEqual(
            catalog.models_by_provider["openai"]["quick"][0].value,
            DEFAULT_QUICK_MODEL,
        )
        self.assertEqual(TICKER_INPUT_EXAMPLES, "Examples: SPY, CNC.TO, 7203.T, 0700.HK")

    def test_cli_and_default_config_read_runtime_defaults(self):
        self.assertEqual(
            ANALYST_ORDER,
            [(option.label, AnalystType(option.value.value)) for option in ANALYST_OPTIONS],
        )
        self.assertEqual(DEFAULT_CONFIG["llm_provider"], DEFAULT_PROVIDER.value)
        self.assertEqual(DEFAULT_CONFIG["backend_url"], DEFAULT_BACKEND_URL)
        self.assertEqual(DEFAULT_CONFIG["quick_think_llm"], DEFAULT_QUICK_MODEL)
        self.assertEqual(DEFAULT_CONFIG["deep_think_llm"], DEFAULT_DEEP_MODEL)
        self.assertEqual(DEFAULT_CONFIG["output_language"], DEFAULT_OUTPUT_LANGUAGE)

    def test_run_request_and_session_snapshot_share_stable_contracts(self):
        request = RunRequest(
            ticker="SPY",
            analysis_date="2026-03-31",
            analysts=[AnalystKey.MARKET, AnalystKey.NEWS],
            research_depth=3,
            llm_provider=ProviderName.OPENAI,
            backend_url=DEFAULT_BACKEND_URL,
            shallow_thinker=DEFAULT_QUICK_MODEL,
            deep_thinker=DEFAULT_DEEP_MODEL,
            output_language=DEFAULT_OUTPUT_LANGUAGE,
        )
        snapshot = SessionSnapshot(
            session_id="run-123",
            request=request,
            selected_inputs={
                "ticker": request.ticker,
                "analysis_date": request.analysis_date,
            },
            status=RunLifecycleState.RUNNING,
            messages=[
                SessionMessage(
                    event_type=EventType.MESSAGE,
                    timestamp="12:00:00",
                    source="Market Analyst",
                    content="Started analysis",
                )
            ],
            tool_calls=[
                ToolCallSnapshot(
                    event_type=EventType.TOOL_CALL,
                    timestamp="12:00:01",
                    source="Market Analyst",
                    tool_name="get_stock_data",
                    arguments={"ticker": "SPY"},
                )
            ],
            report_sections={"market_report": "Draft content"},
        )

        self.assertEqual(snapshot.status, RunLifecycleState.RUNNING)
        self.assertEqual(snapshot.request.llm_provider, ProviderName.OPENAI)
        self.assertEqual(snapshot.request.analysts, [AnalystKey.MARKET, AnalystKey.NEWS])
        self.assertEqual(snapshot.messages[0].event_type, EventType.MESSAGE)
        self.assertEqual(snapshot.tool_calls[0].tool_name, "get_stock_data")
        self.assertEqual(snapshot.report_sections["market_report"], "Draft content")

        another_snapshot = SessionSnapshot()
        another_snapshot.messages.append(SessionMessage(content="Independent"))
        self.assertEqual(len(snapshot.messages), 1)
        self.assertEqual(len(another_snapshot.messages), 1)


if __name__ == "__main__":
    unittest.main()
