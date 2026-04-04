from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple


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


def structured_report_sections_from_final_state(
    final_state: Dict[str, Any],
) -> Dict[str, str]:
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
    if investment_debate.get("bull_history"):
        sections["bull_research"] = str(investment_debate["bull_history"])
    if investment_debate.get("bear_history"):
        sections["bear_research"] = str(investment_debate["bear_history"])
    if investment_debate.get("judge_decision"):
        sections["investment_plan"] = str(investment_debate["judge_decision"])

    risk_debate = final_state.get("risk_debate_state") or {}
    if risk_debate.get("aggressive_history"):
        sections["aggressive_risk"] = str(risk_debate["aggressive_history"])
    if risk_debate.get("conservative_history"):
        sections["conservative_risk"] = str(risk_debate["conservative_history"])
    if risk_debate.get("neutral_history"):
        sections["neutral_risk"] = str(risk_debate["neutral_history"])
    if risk_debate.get("judge_decision"):
        sections["final_trade_decision"] = str(risk_debate["judge_decision"])

    return sections


def build_compiled_report_sections(
    structured_sections: Mapping[str, Any],
) -> List[str]:
    sections: List[str] = []

    analyst_parts: List[Tuple[str, str]] = []
    if structured_sections.get("market_report"):
        analyst_parts.append(("Market Analyst", str(structured_sections["market_report"])))
    if structured_sections.get("sentiment_report"):
        analyst_parts.append(("Social Analyst", str(structured_sections["sentiment_report"])))
    if structured_sections.get("news_report"):
        analyst_parts.append(("News Analyst", str(structured_sections["news_report"])))
    if structured_sections.get("fundamentals_report"):
        analyst_parts.append(
            ("Fundamentals Analyst", str(structured_sections["fundamentals_report"]))
        )
    if analyst_parts:
        sections.append(
            "## I. Analyst Team Reports\n\n"
            + "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        )

    research_parts: List[Tuple[str, str]] = []
    if structured_sections.get("bull_research"):
        research_parts.append(("Bull Researcher", str(structured_sections["bull_research"])))
    if structured_sections.get("bear_research"):
        research_parts.append(("Bear Researcher", str(structured_sections["bear_research"])))
    if structured_sections.get("investment_plan"):
        research_parts.append(("Research Manager", str(structured_sections["investment_plan"])))
    if research_parts:
        sections.append(
            "## II. Research Team Decision\n\n"
            + "\n\n".join(f"### {name}\n{text}" for name, text in research_parts)
        )

    if structured_sections.get("trader_investment_plan"):
        sections.append(
            "## III. Trading Team Plan\n\n"
            f"### Trader\n{structured_sections['trader_investment_plan']}"
        )

    risk_parts: List[Tuple[str, str]] = []
    if structured_sections.get("aggressive_risk"):
        risk_parts.append(("Aggressive Analyst", str(structured_sections["aggressive_risk"])))
    if structured_sections.get("conservative_risk"):
        risk_parts.append(
            ("Conservative Analyst", str(structured_sections["conservative_risk"]))
        )
    if structured_sections.get("neutral_risk"):
        risk_parts.append(("Neutral Analyst", str(structured_sections["neutral_risk"])))
    if risk_parts:
        sections.append(
            "## IV. Risk Management Team Decision\n\n"
            + "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
        )

    if structured_sections.get("final_trade_decision"):
        sections.append(
            "## V. Portfolio Manager Decision\n\n"
            f"### Portfolio Manager\n{structured_sections['final_trade_decision']}"
        )

    return sections


def compile_structured_report(structured_sections: Mapping[str, Any]) -> str | None:
    sections = build_compiled_report_sections(structured_sections)
    if not sections:
        return None
    return "\n\n".join(sections)


def compile_report_sections(final_state: Dict[str, Any]) -> List[str]:
    return build_compiled_report_sections(
        structured_report_sections_from_final_state(final_state)
    )


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
    report_body = compile_structured_report(
        structured_report_sections_from_final_state(final_state)
    )
    if not report_body:
        return header
    return header + "\n\n" + report_body


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
