from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _runtime_report_sections(final_state: Dict[str, Any]) -> Dict[str, str]:
    sections: Dict[str, str] = {}

    for section_name in (
        "market_report",
        "sentiment_report",
        "news_report",
        "fundamentals_report",
        "trader_investment_plan",
    ):
        content = final_state.get(section_name)
        if content:
            sections[section_name] = str(content)

    investment_debate = final_state.get("investment_debate_state") or {}
    if investment_debate.get("judge_decision"):
        sections["investment_plan"] = str(investment_debate["judge_decision"])

    risk_debate = final_state.get("risk_debate_state") or {}
    if risk_debate.get("judge_decision"):
        sections["final_trade_decision"] = str(risk_debate["judge_decision"])

    return sections


def compile_report_sections(final_state: Dict[str, Any]) -> List[str]:
    sections: List[str] = []

    analyst_parts: List[Tuple[str, str]] = []
    if final_state.get("market_report"):
        analyst_parts.append(("Market Analyst", final_state["market_report"]))
    if final_state.get("sentiment_report"):
        analyst_parts.append(("Social Analyst", final_state["sentiment_report"]))
    if final_state.get("news_report"):
        analyst_parts.append(("News Analyst", final_state["news_report"]))
    if final_state.get("fundamentals_report"):
        analyst_parts.append(("Fundamentals Analyst", final_state["fundamentals_report"]))
    if analyst_parts:
        sections.append(
            "## I. Analyst Team Reports\n\n"
            + "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        )

    debate = final_state.get("investment_debate_state") or {}
    research_parts: List[Tuple[str, str]] = []
    if debate.get("bull_history"):
        research_parts.append(("Bull Researcher", debate["bull_history"]))
    if debate.get("bear_history"):
        research_parts.append(("Bear Researcher", debate["bear_history"]))
    if debate.get("judge_decision"):
        research_parts.append(("Research Manager", debate["judge_decision"]))
    if research_parts:
        sections.append(
            "## II. Research Team Decision\n\n"
            + "\n\n".join(f"### {name}\n{text}" for name, text in research_parts)
        )

    if final_state.get("trader_investment_plan"):
        sections.append(
            "## III. Trading Team Plan\n\n"
            f"### Trader\n{final_state['trader_investment_plan']}"
        )

    risk = final_state.get("risk_debate_state") or {}
    risk_parts: List[Tuple[str, str]] = []
    if risk.get("aggressive_history"):
        risk_parts.append(("Aggressive Analyst", risk["aggressive_history"]))
    if risk.get("conservative_history"):
        risk_parts.append(("Conservative Analyst", risk["conservative_history"]))
    if risk.get("neutral_history"):
        risk_parts.append(("Neutral Analyst", risk["neutral_history"]))
    if risk_parts:
        sections.append(
            "## IV. Risk Management Team Decision\n\n"
            + "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
        )

    if risk.get("judge_decision"):
        sections.append(
            "## V. Portfolio Manager Decision\n\n"
            f"### Portfolio Manager\n{risk['judge_decision']}"
        )

    return sections


def compile_complete_report(
    final_state: Dict[str, Any],
    ticker: str,
    *,
    generated_at: dt.datetime | None = None,
) -> str:
    generated_at = generated_at or dt.datetime.now()
    header = (
        f"# Trading Analysis Report: {ticker}\n\n"
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    sections = compile_report_sections(final_state)
    if not sections:
        return header
    return header + "\n\n" + "\n\n".join(sections)


def export_report_bundle(
    final_state: Dict[str, Any],
    ticker: str,
    save_path: Path,
    *,
    generated_at: dt.datetime | None = None,
    runtime_report_dir: Path | None = None,
    runtime_log_file: Path | None = None,
) -> Path:
    save_path.mkdir(parents=True, exist_ok=True)

    analysts_dir = save_path / "1_analysts"
    if final_state.get("market_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "market.md").write_text(final_state["market_report"], encoding="utf-8")
    if final_state.get("sentiment_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "sentiment.md").write_text(
            final_state["sentiment_report"],
            encoding="utf-8",
        )
    if final_state.get("news_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "news.md").write_text(final_state["news_report"], encoding="utf-8")
    if final_state.get("fundamentals_report"):
        analysts_dir.mkdir(exist_ok=True)
        (analysts_dir / "fundamentals.md").write_text(
            final_state["fundamentals_report"],
            encoding="utf-8",
        )

    debate = final_state.get("investment_debate_state") or {}
    research_dir = save_path / "2_research"
    if debate.get("bull_history"):
        research_dir.mkdir(exist_ok=True)
        (research_dir / "bull.md").write_text(debate["bull_history"], encoding="utf-8")
    if debate.get("bear_history"):
        research_dir.mkdir(exist_ok=True)
        (research_dir / "bear.md").write_text(debate["bear_history"], encoding="utf-8")
    if debate.get("judge_decision"):
        research_dir.mkdir(exist_ok=True)
        (research_dir / "manager.md").write_text(debate["judge_decision"], encoding="utf-8")

    if final_state.get("trader_investment_plan"):
        trading_dir = save_path / "3_trading"
        trading_dir.mkdir(exist_ok=True)
        (trading_dir / "trader.md").write_text(
            final_state["trader_investment_plan"],
            encoding="utf-8",
        )

    risk = final_state.get("risk_debate_state") or {}
    risk_dir = save_path / "4_risk"
    if risk.get("aggressive_history"):
        risk_dir.mkdir(exist_ok=True)
        (risk_dir / "aggressive.md").write_text(
            risk["aggressive_history"],
            encoding="utf-8",
        )
    if risk.get("conservative_history"):
        risk_dir.mkdir(exist_ok=True)
        (risk_dir / "conservative.md").write_text(
            risk["conservative_history"],
            encoding="utf-8",
        )
    if risk.get("neutral_history"):
        risk_dir.mkdir(exist_ok=True)
        (risk_dir / "neutral.md").write_text(risk["neutral_history"], encoding="utf-8")
    if risk.get("judge_decision"):
        portfolio_dir = save_path / "5_portfolio"
        portfolio_dir.mkdir(exist_ok=True)
        (portfolio_dir / "decision.md").write_text(risk["judge_decision"], encoding="utf-8")

    report_file = save_path / "complete_report.md"
    report_file.write_text(
        compile_complete_report(
            final_state,
            ticker,
            generated_at=generated_at,
        ),
        encoding="utf-8",
    )

    if runtime_report_dir is not None and runtime_report_dir.exists():
        exported_reports_dir = save_path / "reports"
        exported_reports_dir.mkdir(exist_ok=True)
        for report_path in sorted(runtime_report_dir.glob("*.md")):
            shutil.copy2(report_path, exported_reports_dir / report_path.name)

    runtime_sections = _runtime_report_sections(final_state)
    if runtime_sections:
        exported_reports_dir = save_path / "reports"
        exported_reports_dir.mkdir(exist_ok=True)
        for section_name, content in runtime_sections.items():
            report_path = exported_reports_dir / f"{section_name}.md"
            if not report_path.exists():
                report_path.write_text(content, encoding="utf-8")

    if runtime_log_file is not None and runtime_log_file.exists():
        shutil.copy2(runtime_log_file, save_path / "message_tool.log")

    return report_file
