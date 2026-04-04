import unittest
from unittest.mock import patch

from tradingagents.llm_clients.openai_client import OpenAIClient


class TestOpenAICompatibleClient(unittest.TestCase):
    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_ollama_uses_openai_compatible_default_base_url(self, mock_chat):
        client = OpenAIClient("llama3.1", provider="ollama")

        client.get_llm()

        call_kwargs = mock_chat.call_args[1]
        self.assertEqual(call_kwargs["base_url"], "http://localhost:11434/v1")
        self.assertEqual(call_kwargs["api_key"], "ollama")

    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_ollama_respects_custom_base_url(self, mock_chat):
        client = OpenAIClient(
            "llama3.1",
            provider="ollama",
            base_url="http://ollama.internal:11434/v1",
        )

        client.get_llm()

        call_kwargs = mock_chat.call_args[1]
        self.assertEqual(call_kwargs["base_url"], "http://ollama.internal:11434/v1")


if __name__ == "__main__":
    unittest.main()
