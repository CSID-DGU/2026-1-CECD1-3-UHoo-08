"""search_service intent 분기 테스트. 의존 모듈 모킹."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _meta(pid, name, brand, price=30000):
    return {
        "id": pid,
        "name": name,
        "brand": brand,
        "category": "base",
        "image_url": None,
        "price": price,
    }


class TestSearchServiceProductName:
    @pytest.mark.asyncio
    @patch("services.search_service.search_products_by_name")
    @patch("services.search_service.classify_intent", new_callable=AsyncMock)
    async def test_product_name_path(self, mock_intent, mock_by_name):
        from services.search_service import run_search

        mock_intent.return_value = "PRODUCT_NAME"
        mock_by_name.return_value = [
            _meta("p1", "네오쿠션 21N", "LANEIGE"),
            _meta("p2", "네오쿠션 23N", "LANEIGE"),
        ]

        result = await run_search("라네즈 네오쿠션")
        assert result["intent"] == "PRODUCT_NAME"
        assert result["category"] is None
        assert len(result["products"]) == 2
        # 상품명 매칭은 matchScore 100 고정
        assert result["products"][0]["matchScore"] == 100

    @pytest.mark.asyncio
    @patch("services.search_service.search_products_by_name")
    @patch("services.search_service.classify_intent", new_callable=AsyncMock)
    async def test_product_name_no_result(self, mock_intent, mock_by_name):
        from services.search_service import run_search

        mock_intent.return_value = "PRODUCT_NAME"
        mock_by_name.return_value = []

        result = await run_search("없는상품명")
        assert result["intent"] == "PRODUCT_NAME"
        assert result["products"] == []


class TestSearchServiceRecommendation:
    @pytest.mark.asyncio
    @patch("services.search_service.get_products_meta")
    @patch("services.search_service.match_products")
    @patch("services.search_service.EmbeddingService")
    @patch("services.search_service.parse_query", new_callable=AsyncMock)
    @patch("services.search_service.classify_intent", new_callable=AsyncMock)
    async def test_recommendation_path(
        self, mock_intent, mock_parse, mock_emb_cls, mock_match, mock_metas
    ):
        from services.search_service import run_search

        mock_intent.return_value = "RECOMMENDATION"
        mock_parse.return_value = {
            "category": "base",
            "features": {"product_type": "쿠션", "finish": "세미매트"},
        }
        emb = MagicMock()
        emb.embed.return_value = [0.1] * 1024
        mock_emb_cls.get.return_value = emb
        mock_match.return_value = [
            {"product_id": "p1", "similarity": 0.95},
            {"product_id": "p2", "similarity": 0.80},
        ]
        mock_metas.return_value = {
            "p1": _meta("p1", "네오쿠션", "LANEIGE"),
            "p2": _meta("p2", "미샤쿠션", "MISSHA", 14000),
        }

        result = await run_search("세미매트 쿠션 추천해줘")
        assert result["intent"] == "RECOMMENDATION"
        assert result["category"] == "base"
        assert len(result["products"]) == 2
        assert result["products"][0]["matchScore"] == 95

    @pytest.mark.asyncio
    @patch("services.search_service.match_products")
    @patch("services.search_service.EmbeddingService")
    @patch("services.search_service.parse_query", new_callable=AsyncMock)
    @patch("services.search_service.classify_intent", new_callable=AsyncMock)
    async def test_recommendation_no_matches(
        self, mock_intent, mock_parse, mock_emb_cls, mock_match
    ):
        from services.search_service import run_search

        mock_intent.return_value = "RECOMMENDATION"
        mock_parse.return_value = {"category": "base", "features": {}}
        emb = MagicMock()
        emb.embed.return_value = [0.1] * 1024
        mock_emb_cls.get.return_value = emb
        mock_match.return_value = []

        result = await run_search("쿠션")
        assert result["intent"] == "RECOMMENDATION"
        assert result["products"] == []

    @pytest.mark.asyncio
    async def test_empty_query(self):
        from services.search_service import run_search

        result = await run_search("   ")
        assert result["products"] == []