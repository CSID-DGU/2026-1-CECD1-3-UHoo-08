"""search_service 단위 테스트 (전부 모킹)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.search_service import search


@pytest.fixture()
def mock_pipeline():
    """query_parser, embedding, match_products, product_reader 전체 모킹."""
    with (
        patch("services.search_service.parse_query", new_callable=AsyncMock) as mock_parse,
        patch("services.search_service.EmbeddingService.get") as mock_emb_get,
        patch("services.search_service.match_products") as mock_match,
        patch("services.search_service.get_products_meta") as mock_meta,
    ):
        mock_emb = MagicMock()
        mock_emb.embed.return_value = [0.1] * 1024
        mock_emb_get.return_value = mock_emb

        yield mock_parse, mock_emb, mock_match, mock_meta


@pytest.mark.asyncio
async def test_search_returns_products(mock_pipeline):
    mock_parse, mock_emb, mock_match, mock_meta = mock_pipeline

    mock_parse.return_value = {
        "category": "base",
        "features": {"product_type": "쿠션", "coverage": "가벼운"},
    }
    mock_match.return_value = [
        {"product_id": "prod-1", "similarity": 0.91},
        {"product_id": "prod-2", "similarity": 0.85},
    ]
    mock_meta.return_value = {
        "prod-1": {"name": "쿠션A", "brand": "브랜드X", "category": "base", "image_url": None, "price": 25000},
        "prod-2": {"name": "쿠션B", "brand": "브랜드Y", "category": "base", "image_url": None, "price": 18000},
    }

    result = await search("여름 가벼운 쿠션 추천해줘")

    assert result["query"] == "여름 가벼운 쿠션 추천해줘"
    assert result["category"] == "base"
    assert len(result["products"]) == 2
    assert result["products"][0]["matchScore"] == 91
    assert result["products"][0]["productId"] == "prod-1"


@pytest.mark.asyncio
async def test_search_match_score_calculation(mock_pipeline):
    mock_parse, mock_emb, mock_match, mock_meta = mock_pipeline

    mock_parse.return_value = {"category": "lip", "features": {"product_type": "틴트"}}
    mock_match.return_value = [{"product_id": "lip-1", "similarity": 0.756}]
    mock_meta.return_value = {
        "lip-1": {"name": "틴트Z", "brand": "코스메틱", "category": "lip", "image_url": None, "price": None}
    }

    result = await search("오래가는 틴트")

    assert result["products"][0]["matchScore"] == 76  # round(0.756 * 100)


@pytest.mark.asyncio
async def test_search_skips_missing_meta(mock_pipeline):
    mock_parse, mock_emb, mock_match, mock_meta = mock_pipeline

    mock_parse.return_value = {"category": "sun", "features": {}}
    mock_match.return_value = [
        {"product_id": "sun-1", "similarity": 0.9},
        {"product_id": "sun-missing", "similarity": 0.8},
    ]
    mock_meta.return_value = {
        "sun-1": {"name": "선크림A", "brand": "B", "category": "sun", "image_url": None, "price": None}
        # sun-missing 없음
    }

    result = await search("선크림 추천")

    assert len(result["products"]) == 1
    assert result["products"][0]["productId"] == "sun-1"


@pytest.mark.asyncio
async def test_search_fallback_on_empty_features(mock_pipeline):
    mock_parse, mock_emb, mock_match, mock_meta = mock_pipeline

    mock_parse.return_value = {"category": "skincare", "features": {}}
    mock_match.return_value = []
    mock_meta.return_value = {}

    result = await search("피부에 좋은 거")

    # feature_text 비어 → 원문 쿼리로 embed 호출 확인
    mock_emb.embed.assert_called_once_with("피부에 좋은 거")
    assert result["products"] == []


@pytest.mark.asyncio
async def test_search_default_category_on_missing(mock_pipeline):
    mock_parse, mock_emb, mock_match, mock_meta = mock_pipeline

    mock_parse.return_value = {}  # category 없음
    mock_match.return_value = []
    mock_meta.return_value = {}

    result = await search("모르는 쿼리")

    assert result["category"] == "base"
