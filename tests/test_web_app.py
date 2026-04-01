import unittest
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


if __name__ == "__main__":
    unittest.main()
