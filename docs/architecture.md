# TradingAgents Architecture

This document maps the current application architecture from the codebase. The diagrams focus on how the CLI and Python entrypoints feed the LangGraph workflow, how agent roles collaborate, and where provider and market-data abstractions sit.

## 1. System Context

```mermaid
flowchart LR
    user["User"]

    subgraph entry["Entry Points"]
        cli["CLI<br/>tradingagents or python -m cli.main"]
        py["Python API<br/>main.py or direct import"]
    end

    subgraph app["Application Core"]
        tgGraph["TradingAgentsGraph"]
        setup["GraphSetup<br/>compiles LangGraph workflow"]
        propagate["Propagator<br/>builds initial state"]
        signal["SignalProcessor<br/>extracts final rating"]
        reflect["Reflector<br/>post-trade learning"]
    end

    subgraph agents["Agent Workflow"]
        analysts["Analysts<br/>market, social, news, fundamentals"]
        research["Research Debate<br/>bull, bear, research manager"]
        trader["Trader"]
        risk["Risk Debate<br/>aggressive, conservative, neutral"]
        pm["Portfolio Manager"]
    end

    subgraph llm["LLM Layer"]
        factory["LLM Client Factory"]
        providers["Providers<br/>OpenAI, Google, Anthropic,<br/>xAI, OpenRouter, Ollama"]
    end

    subgraph data["Market Data Layer"]
        tools["LangGraph Tool Nodes"]
        router["Dataflow Router"]
        vendors["Vendors<br/>yfinance, Alpha Vantage"]
    end

    subgraph storage["State and Artifacts"]
        memory["BM25 Memories<br/>per role"]
        logs["JSON Run Logs<br/>eval_results/..."]
        cache["Data Cache<br/>tradingagents/dataflows/data_cache"]
    end

    user --> cli
    user --> py
    cli --> tgGraph
    py --> tgGraph

    tgGraph --> propagate
    tgGraph --> setup
    setup --> analysts
    analysts --> research
    research --> trader
    trader --> risk
    risk --> pm
    pm --> signal
    tgGraph --> reflect

    tgGraph --> factory
    factory --> providers

    analysts --> tools
    tools --> router
    router --> vendors
    vendors --> cache

    research --> memory
    trader --> memory
    pm --> memory
    tgGraph --> logs
```

## 2. Package Structure and Responsibilities

```mermaid
flowchart TB
    subgraph interfaces["Interfaces"]
        cliMain["cli/main.py<br/>interactive terminal UX"]
        cliSupport["cli/utils.py, cli/models.py,<br/>cli/stats_handler.py"]
        pyEntry["main.py<br/>example script"]
    end

    subgraph orchestration["Graph Orchestration"]
        tg["tradingagents/graph/trading_graph.py"]
        gs["graph/setup.py<br/>node and edge assembly"]
        cond["graph/conditional_logic.py<br/>loop control"]
        prop["graph/propagation.py<br/>initial state"]
        sig["graph/signal_processing.py<br/>normalize decision"]
        refl["graph/reflection.py<br/>feedback loop"]
    end

    subgraph agents["Agent Nodes"]
        analysts["agents/analysts/*<br/>report-producing tool users"]
        researchers["agents/researchers/*<br/>bull and bear debate"]
        managers["agents/managers/*<br/>research manager and portfolio manager"]
        trader["agents/trader/trader.py<br/>transaction proposal"]
        risk["agents/risk_mgmt/*<br/>three-way risk debate"]
    end

    subgraph shared["Shared Agent Utilities"]
        states["agents/utils/agent_states.py<br/>LangGraph shared state"]
        utils["agents/utils/agent_utils.py<br/>tool exports, ticker context,<br/>language behavior, message cleanup"]
        mem["agents/utils/memory.py<br/>BM25 memory retrieval"]
    end

    subgraph integration["Integration Layer"]
        llmFactory["llm_clients/factory.py"]
        llmClients["provider clients + model catalog"]
        dataInterface["dataflows/interface.py<br/>vendor routing and fallback"]
        dataSources["vendor modules<br/>y_finance* and alpha_vantage*"]
        config["default_config.py + dataflows/config.py"]
    end

    interfaces --> orchestration
    orchestration --> agents
    agents --> shared
    orchestration --> shared
    orchestration --> integration
    shared --> integration
    dataInterface --> dataSources
    llmFactory --> llmClients
    config --> orchestration
    config --> dataInterface
```

## 3. Runtime Execution Flow

```mermaid
flowchart TD
    start["Start analysis<br/>Ticker + trade date + config"]
    init["Propagator creates AgentState<br/>reports empty, debate state reset"]

    market["Market Analyst"]
    marketTools["Market tools<br/>get_stock_data, get_indicators"]

    social["Social Analyst"]
    socialTools["Social tool<br/>get_news"]

    news["News Analyst"]
    newsTools["News tools<br/>get_news, get_global_news,<br/>get_insider_transactions"]

    fundamentals["Fundamentals Analyst"]
    fundamentalsTools["Fundamental tools<br/>get_fundamentals, statements"]

    bull["Bull Researcher"]
    bear["Bear Researcher"]
    judge["Research Manager"]

    trade["Trader"]

    aggressive["Aggressive Analyst"]
    conservative["Conservative Analyst"]
    neutral["Neutral Analyst"]
    portfolio["Portfolio Manager"]

    decision["Final trade narrative"]
    rating["SignalProcessor extracts<br/>BUY / OVERWEIGHT / HOLD /<br/>UNDERWEIGHT / SELL"]
    logs["Run logged to JSON"]

    start --> init --> market

    market --> marketCheck{"Tool call?"}
    marketCheck -->|yes| marketTools --> market
    marketCheck -->|no| social

    social --> socialCheck{"Tool call?"}
    socialCheck -->|yes| socialTools --> social
    socialCheck -->|no| news

    news --> newsCheck{"Tool call?"}
    newsCheck -->|yes| newsTools --> news
    newsCheck -->|no| fundamentals

    fundamentals --> fundamentalsCheck{"Tool call?"}
    fundamentalsCheck -->|yes| fundamentalsTools --> fundamentals
    fundamentalsCheck -->|no| bull

    bull --> debateCheck{"Debate rounds complete?"}
    debateCheck -->|no| bear --> bull
    debateCheck -->|yes| judge

    judge --> trade
    trade --> aggressive

    aggressive --> riskCheckA{"Risk rounds complete?"}
    riskCheckA -->|no| conservative
    riskCheckA -->|yes| portfolio

    conservative --> riskCheckC{"Risk rounds complete?"}
    riskCheckC -->|no| neutral
    riskCheckC -->|yes| portfolio

    neutral --> riskCheckN{"Risk rounds complete?"}
    riskCheckN -->|no| aggressive
    riskCheckN -->|yes| portfolio

    portfolio --> decision --> rating
    portfolio --> logs
```

## 4. State and Information Flow

```mermaid
flowchart LR
    ticker["Ticker + trade date"]
    reports["Analyst reports<br/>market, sentiment, news, fundamentals"]
    investState["investment_debate_state<br/>history, current response,<br/>judge decision, count"]
    plan["investment_plan"]
    traderPlan["trader_investment_plan"]
    riskState["risk_debate_state<br/>histories, latest speaker,<br/>judge decision, count"]
    finalDecision["final_trade_decision"]

    ticker --> reports
    reports --> investState
    investState --> plan
    reports --> traderPlan
    plan --> traderPlan
    reports --> riskState
    traderPlan --> riskState
    riskState --> finalDecision
```

## 5. Key Architectural Notes

- The application is centered on `TradingAgentsGraph`, which owns configuration, LLM client construction, memory instances, tool-node registration, graph compilation, logging, and optional reflection.
- Analyst nodes are the only role layer that uses LangGraph `ToolNode`s directly. They iterate until the LLM stops issuing tool calls, then write a finalized report back into shared state.
- Debate-driven roles do not call tools directly. They consume analyst reports plus memory retrievals and update nested debate state objects.
- The graph is intentionally sequential in the analyst phase. The selected analyst order determines execution order, and omitted analysts are removed from the runtime graph entirely.
- Market-data access is abstracted through `dataflows/interface.py`, which routes each method to a configured vendor and only falls back automatically when Alpha Vantage rate limits occur.
- LLM access is abstracted through `llm_clients/factory.py`, allowing the same graph to run against multiple providers while preserving provider-specific knobs like OpenAI reasoning effort or Anthropic effort.
- The CLI is a presentation layer over the same graph. It adds questionary-based configuration, Rich live rendering, announcements, and callback-based token/tool statistics, but it does not change the workflow semantics.
