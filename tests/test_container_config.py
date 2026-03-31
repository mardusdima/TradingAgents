import unittest
from pathlib import Path


class ContainerConfigTests(unittest.TestCase):
    def test_compose_defines_separate_agents_and_web_services(self):
        compose = Path("compose.yaml").read_text(encoding="utf-8")

        self.assertIn("tradingagents:", compose)
        self.assertIn("tradingagents-web:", compose)
        self.assertIn('command: ["tradingagents", "analyze"]', compose)
        self.assertIn('command: ["tradingagents", "ui", "--host", "0.0.0.0", "--port", "8000"]', compose)
        self.assertIn('- "8000:8000"', compose)

    def test_dockerfile_exposes_web_port(self):
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("EXPOSE 8000", dockerfile)


if __name__ == "__main__":
    unittest.main()
