import unittest
from unittest.mock import patch

from cli.main import start_ui_server


class UiEntrypointTests(unittest.TestCase):
    @patch("cli.main.uvicorn.run")
    def test_start_ui_server_launches_fastapi_app(self, mock_run):
        start_ui_server(host="127.0.0.1", port=8123, reload=True)

        mock_run.assert_called_once_with(
            "tradingagents.ui.main:app",
            host="127.0.0.1",
            port=8123,
            reload=True,
        )


if __name__ == "__main__":
    unittest.main()
