from __future__ import annotations

from cli.stats_handler import StatsCallbackHandler

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

from .models import AnalysisRequest, RunStats


def build_graph_config(request: AnalysisRequest) -> dict:
    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = request.research_depth
    config["max_risk_discuss_rounds"] = request.research_depth
    config["quick_think_llm"] = request.shallow_thinker
    config["deep_think_llm"] = request.deep_thinker
    config["backend_url"] = request.backend_url
    config["llm_provider"] = request.llm_provider
    config["google_thinking_level"] = request.google_thinking_level
    config["openai_reasoning_effort"] = request.openai_reasoning_effort
    config["anthropic_effort"] = request.anthropic_effort
    config["output_language"] = request.output_language
    return config


class GraphAnalysisBackend:
    """Production backend that streams chunks from TradingAgentsGraph."""

    def __init__(self, request: AnalysisRequest):
        self.request = request
        self.stats_handler = StatsCallbackHandler()
        self.graph = TradingAgentsGraph(
            request.analysts,
            config=build_graph_config(request),
            debug=True,
            callbacks=[self.stats_handler],
        )

    def stream(self, request: AnalysisRequest):
        init_agent_state = self.graph.propagator.create_initial_state(
            request.ticker,
            request.analysis_date,
        )
        args = self.graph.propagator.get_graph_args(callbacks=[self.stats_handler])
        for chunk in self.graph.graph.stream(init_agent_state, **args):
            yield chunk

    def get_stats(self):
        stats = self.stats_handler.get_stats()
        return RunStats(**stats)
