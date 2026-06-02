"""query_parser 단위 테스트. qwen_client 모킹."""
from unittest.mock import AsyncMock, patch

import pytest


class TestQueryParser:
    @pytest.mark.asyncio
    @patch("services.query_parser.get_qwen_llm")
    async def test_valid_parse(self, mock_get):
        from services.query_parser import parse_query

        llm = AsyncMock()
        llm.chat_json.return_value = {
            "category": "base",
            "features": {"product_type": "쿠션", "finish": "세미매트"},
        }
        mock_get.return_value = llm

        result = await parse_query("세미매트 쿠션 추천해줘")
        assert result["category"] == "base"
        assert result["features"]["product_type"] == "쿠션"

    @pytest.mark.asyncio
    @patch("services.query_parser.get_qwen_llm")
    async def test_llm_returns_none(self, mock_get):
        from services.query_parser import parse_query

        llm = AsyncMock()
        llm.chat_json.return_value = None
        mock_get.return_value = llm

        result = await parse_query("음 그냥 뭔가")
        assert result["category"] is None
        assert result["features"] == {}

    @pytest.mark.asyncio
    @patch("services.query_parser.get_qwen_llm")
    async def test_invalid_category_nulled(self, mock_get):
        from services.query_parser import parse_query

        llm = AsyncMock()
        llm.chat_json.return_value = {"category": "makeup_remover", "features": {}}
        mock_get.return_value = llm

        result = await parse_query("클렌징 워터")
        assert result["category"] is None

    @pytest.mark.asyncio
    @patch("services.query_parser.get_qwen_llm")
    async def test_features_not_dict_handled(self, mock_get):
        from services.query_parser import parse_query

        llm = AsyncMock()
        llm.chat_json.return_value = {"category": "lip", "features": "이상한값"}
        mock_get.return_value = llm

        result = await parse_query("틴트")
        assert result["category"] == "lip"
        assert result["features"] == {}

    @pytest.mark.asyncio
    async def test_empty_query(self):
        from services.query_parser import parse_query

        result = await parse_query("   ")
        assert result["category"] is None
        assert result["features"] == {}
