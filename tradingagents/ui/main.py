from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from cli.announcements import fetch_announcements
from tradingagents.app.backend import GraphAnalysisBackend
from tradingagents.app.history import AnalysisHistoryRepository
from tradingagents.app.importer import LegacyAnalysisImporter
from tradingagents.app.models import AnalysisRequest
from tradingagents.app.service import AnalysisRunService, SingleRunCoordinator
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients.model_catalog import MODEL_OPTIONS


TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(
    *,
    repository: Optional[AnalysisHistoryRepository] = None,
    coordinator: Optional[SingleRunCoordinator] = None,
    announcements_provider: Optional[Callable[[], dict]] = None,
) -> FastAPI:
    using_defaults = repository is None and coordinator is None and announcements_provider is None
    repository = repository or AnalysisHistoryRepository(Path(DEFAULT_CONFIG["results_dir"]))
    if coordinator is None:
        service = AnalysisRunService(repository, backend_factory=GraphAnalysisBackend)
        coordinator = SingleRunCoordinator(service)
    announcements_provider = announcements_provider or (
        fetch_announcements if using_defaults else (lambda: {"announcements": [], "require_attention": False})
    )

    if using_defaults:
        LegacyAnalysisImporter(Path.cwd(), repository).import_existing()

    app = FastAPI(title="TradingAgents UI")
    app.state.repository = repository
    app.state.coordinator = coordinator
    app.state.announcements_provider = announcements_provider

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        runs = repository.list_runs()
        announcements = announcements_provider()
        return TEMPLATES.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "runs": runs[:10],
                "announcements": announcements.get("announcements", []),
                "require_attention": announcements.get("require_attention", False),
                "form_data": default_form_data(),
                "providers": MODEL_OPTIONS,
                "error_message": None,
            },
        )

    @app.post("/runs", response_class=HTMLResponse)
    async def start_run(
        request: Request,
        ticker: str = Form(...),
        analysis_date: str = Form(...),
        analysts: list[str] = Form(...),
        research_depth: int = Form(...),
        llm_provider: str = Form(...),
        backend_url: str = Form(""),
        shallow_thinker: str = Form(""),
        deep_thinker: str = Form(""),
        google_thinking_level: Optional[str] = Form(None),
        openai_reasoning_effort: Optional[str] = Form(None),
        anthropic_effort: Optional[str] = Form(None),
        output_language: str = Form("English"),
    ):
        form_data = {
            "ticker": ticker,
            "analysis_date": analysis_date,
            "analysts": analysts,
            "research_depth": research_depth,
            "llm_provider": llm_provider,
            "backend_url": backend_url,
            "shallow_thinker": shallow_thinker,
            "deep_thinker": deep_thinker,
            "google_thinking_level": google_thinking_level,
            "openai_reasoning_effort": openai_reasoning_effort,
            "anthropic_effort": anthropic_effort,
            "output_language": output_language,
        }
        analysis_request = AnalysisRequest(**form_data)
        try:
            run_id = coordinator.start(analysis_request, source="ui")
        except RuntimeError as exc:
            return TEMPLATES.TemplateResponse(
                request,
                "dashboard.html",
                {
                    "request": request,
                    "runs": repository.list_runs()[:10],
                    "announcements": announcements_provider().get("announcements", []),
                    "require_attention": announcements_provider().get("require_attention", False),
                    "form_data": analysis_request.to_dict(),
                    "providers": MODEL_OPTIONS,
                    "error_message": str(exc),
                },
                status_code=409,
            )

        return RedirectResponse(url=f"/runs/{run_id}", status_code=303)

    @app.get("/history", response_class=HTMLResponse)
    def history(
        request: Request,
        ticker: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        rating: Optional[str] = Query(None),
    ):
        runs = repository.list_runs(ticker=ticker, status=status, rating=rating)
        return TEMPLATES.TemplateResponse(
            request,
            "history.html",
            {
                "request": request,
                "runs": runs,
                "filters": {"ticker": ticker or "", "status": status or "", "rating": rating or ""},
            },
        )

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(request: Request, run_id: str):
        detail = repository.get_run_detail(run_id)
        return TEMPLATES.TemplateResponse(
            request,
            "run_detail.html",
            {
                "request": request,
                "detail": detail,
                "active_run_id": coordinator.active_run_id,
            },
        )

    @app.get("/runs/{run_id}/rerun", response_class=HTMLResponse)
    def rerun(request: Request, run_id: str):
        detail = repository.get_run_detail(run_id)
        return TEMPLATES.TemplateResponse(
            request,
            "dashboard.html",
            {
                "request": request,
                "runs": repository.list_runs()[:10],
                "announcements": announcements_provider().get("announcements", []),
                "require_attention": announcements_provider().get("require_attention", False),
                "form_data": detail.summary.request.to_dict(),
                "providers": MODEL_OPTIONS,
                "error_message": None,
            },
        )

    @app.get("/runs/{run_id}/download")
    def download_report(run_id: str):
        artifact = Path(repository.get_run_detail(run_id).artifact_dir) / "complete_report.md"
        return FileResponse(artifact, media_type="text/markdown", filename=f"{run_id}.md")

    @app.get("/runs/{run_id}/fragments/status", response_class=HTMLResponse)
    def status_fragment(request: Request, run_id: str):
        detail = repository.get_run_detail(run_id)
        return TEMPLATES.TemplateResponse(
            request,
            "fragments/status.html",
            {"request": request, "detail": detail},
        )

    @app.get("/runs/{run_id}/fragments/sections", response_class=HTMLResponse)
    def sections_fragment(request: Request, run_id: str):
        detail = repository.get_run_detail(run_id)
        return TEMPLATES.TemplateResponse(
            request,
            "fragments/sections.html",
            {"request": request, "detail": detail},
        )

    @app.get("/runs/{run_id}/fragments/events", response_class=HTMLResponse)
    def events_fragment(request: Request, run_id: str):
        detail = repository.get_run_detail(run_id)
        return TEMPLATES.TemplateResponse(
            request,
            "fragments/events.html",
            {"request": request, "detail": detail},
        )

    @app.get("/runs/{run_id}/fragments/stats", response_class=HTMLResponse)
    def stats_fragment(request: Request, run_id: str):
        detail = repository.get_run_detail(run_id)
        return TEMPLATES.TemplateResponse(
            request,
            "fragments/stats.html",
            {"request": request, "detail": detail},
        )

    return app


def default_form_data() -> dict:
    return {
        "ticker": "SPY",
        "analysis_date": "",
        "analysts": ["market", "social", "news", "fundamentals"],
        "research_depth": 3,
        "llm_provider": "openai",
        "backend_url": DEFAULT_CONFIG["backend_url"],
        "shallow_thinker": DEFAULT_CONFIG["quick_think_llm"],
        "deep_thinker": DEFAULT_CONFIG["deep_think_llm"],
        "google_thinking_level": None,
        "openai_reasoning_effort": DEFAULT_CONFIG.get("openai_reasoning_effort"),
        "anthropic_effort": DEFAULT_CONFIG.get("anthropic_effort"),
        "output_language": DEFAULT_CONFIG.get("output_language", "English"),
    }


app = create_app()
