from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from tradingagents.web.api import TradingAgentsWebService, create_api_router

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app(service: TradingAgentsWebService | None = None) -> FastAPI:
    app = FastAPI(title="TradingAgents Web UI")
    app.state.web_service = service or TradingAgentsWebService()
    app.include_router(create_api_router())
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return TEMPLATES_DIR.joinpath("index.html").read_text(encoding="utf-8")

    return app


app = create_app()
