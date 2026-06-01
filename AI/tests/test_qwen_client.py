"""qwen_client 단위 테스트. OpenAI SDK 호출 모킹."""
from unittest.mock import MagicMock, patch

import pytest


class TestQwenClient:
    @pytest.mark.asyncio
    @patch("services.qwen_client.OpenAI")
    async def test_chat_returns_content(self, mock_openai_cls):
        from services.qwen_client import QwenLLMClient

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="hello"))]
        )
        mock_openai_cls.return_value = client_mock

        c = QwenLLMClient()
        out = await c.chat(system="s", user="u")
        assert out == "hello"

    @pytest.mark.asyncio
    @patch("services.qwen_client.OpenAI")
    async def test_chat_json_parses(self, mock_openai_cls):
        from services.qwen_client import QwenLLMClient

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"a": 1}'))]
        )
        mock_openai_cls.return_value = client_mock

        c = QwenLLMClient()
        out = await c.chat_json(system="s", user="u")
        assert out == {"a": 1}

    @pytest.mark.asyncio
    @patch("services.qwen_client.OpenAI")
    async def test_chat_json_handles_code_fence(self, mock_openai_cls):
        from services.qwen_client import QwenLLMClient

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='```json\n{"a": 1}\n```'))]
        )
        mock_openai_cls.return_value = client_mock

        c = QwenLLMClient()
        out = await c.chat_json(system="s", user="u")
        assert out == {"a": 1}

    @pytest.mark.asyncio
    @patch("services.qwen_client.OpenAI")
    async def test_chat_json_returns_none_on_parse_error(self, mock_openai_cls):
        from services.qwen_client import QwenLLMClient

        client_mock = MagicMock()
        client_mock.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json"))]
        )
        mock_openai_cls.return_value = client_mock

        c = QwenLLMClient()
        out = await c.chat_json(system="s", user="u")
        assert out is None