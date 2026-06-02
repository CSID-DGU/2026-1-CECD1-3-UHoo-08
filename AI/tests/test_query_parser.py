"""query_parser 단위 테스트 (전부 모킹)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.query_parser import parse_query


@pytest.mark.asyncio
async def test_parse_query_base_cushion():
    mock_result = {"category": "base", "features": {"product_type": "쿠션", "coverage": "가벼운"}}
    with patch("services.query_parser.get_qwen_llm") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat_json = AsyncMock(return_value=mock_result)
        mock_get.return_value = mock_client

        result = await parse_query("여름 가벼운 쿠션 추천해줘")

    assert result["category"] == "base"
    assert result["features"]["product_type"] == "쿠션"
    assert result["features"]["coverage"] == "가벼운"


@pytest.mark.asyncio
async def test_parse_query_sun():
    mock_result = {"category": "sun", "features": {"product_type": "선크림", "finish": "매트"}}
    with patch("services.query_parser.get_qwen_llm") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat_json = AsyncMock(return_value=mock_result)
        mock_get.return_value = mock_client

        result = await parse_query("매트한 선크림 알려줘")

    assert result["category"] == "sun"
    assert result["features"]["finish"] == "매트"


@pytest.mark.asyncio
async def test_parse_query_lip():
    mock_result = {"category": "lip", "features": {"product_type": "틴트", "lasting_power": "높음"}}
    with patch("services.query_parser.get_qwen_llm") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat_json = AsyncMock(return_value=mock_result)
        mock_get.return_value = mock_client

        result = await parse_query("오래 유지되는 틴트 추천")

    assert result["category"] == "lip"
    assert result["features"]["lasting_power"] == "높음"


@pytest.mark.asyncio
async def test_parse_query_skincare():
    mock_result = {
        "category": "skincare",
        "features": {"product_type": "세럼", "texture": "가벼운", "skin_type": "지성"},
    }
    with patch("services.query_parser.get_qwen_llm") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat_json = AsyncMock(return_value=mock_result)
        mock_get.return_value = mock_client

        result = await parse_query("지성 피부용 가벼운 세럼")

    assert result["category"] == "skincare"
    assert result["features"]["skin_type"] == "지성"


@pytest.mark.asyncio
async def test_parse_query_returns_empty_on_llm_none():
    with patch("services.query_parser.get_qwen_llm") as mock_get:
        mock_client = AsyncMock()
        mock_client.chat_json = AsyncMock(return_value=None)
        mock_get.return_value = mock_client

        result = await parse_query("알 수 없는 입력")

    assert result == {}
