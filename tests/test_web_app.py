import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from tradingagents.web.app import create_app, main


class WebAppTests(unittest.TestCase):
    def test_create_app_exposes_expected_routes(self):
        app = create_app()
        routes = {route.path for route in app.routes}

        self.assertIn("/", routes)
        self.assertIn("/health", routes)
        self.assertIn("/api/options", routes)
        self.assertIn("/api/runs", routes)
        self.assertIn("/api/runs/{session_id}", routes)

    def test_main_runs_uvicorn_with_defaults(self):
        with patch("uvicorn.run") as run_mock:
            main([])

        run_mock.assert_called_once_with(
            "tradingagents.web.app:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
        )

    def test_main_accepts_host_port_and_reload_arguments(self):
        with patch("uvicorn.run") as run_mock:
            main(["--host", "0.0.0.0", "--port", "9000", "--reload"])

        run_mock.assert_called_once_with(
            "tradingagents.web.app:app",
            host="0.0.0.0",
            port=9000,
            reload=True,
        )

    def test_web_assets_are_declared_as_package_data(self):
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

        package_data = pyproject["tool"]["setuptools"]["package-data"]

        self.assertEqual(package_data["cli"], ["static/*"])
        self.assertEqual(
            package_data["tradingagents"],
            ["web/static/*", "web/templates/*"],
        )

    def test_validation_error_targets_match_runtime_field_names(self):
        web_dir = Path(__file__).resolve().parents[1] / "tradingagents" / "web"
        template = (web_dir / "templates" / "index.html").read_text(encoding="utf-8")
        script = (web_dir / "static" / "app.js").read_text(encoding="utf-8")

        for field in (
            "ticker",
            "analysis_date",
            "output_language",
            "research_depth",
            "llm_provider",
            "shallow_thinker",
            "deep_thinker",
            "analysts",
        ):
            self.assertIn(f'id="{field}-error"', template)

        self.assertIn("const FIELD_ERROR_TARGETS = {", script)
        self.assertIn('google_thinking_level: "provider-specific-error"', script)
        self.assertIn('openai_reasoning_effort: "provider-specific-error"', script)
        self.assertIn('anthropic_effort: "provider-specific-error"', script)


if __name__ == "__main__":
    unittest.main()
