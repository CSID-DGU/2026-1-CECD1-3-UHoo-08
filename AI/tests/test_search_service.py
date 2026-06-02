"""search_service 단위 테스트. 의존 모듈 모킹."""
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


class TestSearchService:
    @pytest.mark.asyncio
    @patch("services.search_service.get_products_meta")
    @patch("services.search_service.match_products")
    @patch("services.search_service.EmbeddingService")
    @patch("services.search_service.parse_query", new_callable=AsyncMock)
    async def test_full_flow(self, mock_parse, mock_emb_cls, mock_match, mock_metas):
        from services.search_service import run_search

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
        assert result["category"] == "base"
        assert len(result["products"]) == 2
        # similarity 내림차순 그대로, matchScore = round(sim*100)
        assert result["products"][0]["matchScore"] == 95
        assert result["products"][0]["productId"] == "p1"
        assert result["products"][1]["matchScore"] == 80

    @pytest.mark.asyncio
    async def test_empty_query(self):
        from services.search_service import run_search

        result = await run_search("   ")
        assert result["products"] == []
        assert result["category"] is None

    @pytest.mark.asyncio
    @patch("services.search_service.match_products")
    @patch("services.search_service.EmbeddingService")
    @patch("services.search_service.parse_query", new_callable=AsyncMock)
    async def test_no_matches(self, mock_parse, mock_emb_cls, mock_match):
        from services.search_service import run_search

        mock_parse.return_value = {"category": "base", "features": {}}
        emb = MagicMock()
        emb.embed.return_value = [0.1] * 1024
        mock_emb_cls.get.return_value = emb
        mock_match.return_value = []

        result = await run_search("쿠션")
        assert result["products"] == []
        assert result["category"] == "base"

    @pytest.mark.asyncio
    @patch("services.search_service.get_products_meta")
    @patch("services.search_service.match_products")
    @patch("services.search_service.EmbeddingService")
    @patch("services.search_service.parse_query", new_callable=AsyncMock)
    async def test_category_none_searches_all(
        self, mock_parse, mock_emb_cls, mock_match, mock_metas
    ):
        from services.search_service import run_search

        # 카테고리 판단 불가 → None으로 전체 검색
        mock_parse.return_value = {"category": None, "features": {}}
        emb = MagicMock()
        emb.embed.return_value = [0.1] * 1024
        mock_emb_cls.get.return_value = emb
        mock_match.return_value = [{"product_id": "p1", "similarity": 0.7}]
        mock_metas.return_value = {"p1": _meta("p1", "토너", "브랜드")}

        result = await run_search("촉촉한 거 추천")
        # match_products에 category=None 전달됐는지
        args = mock_match.call_args.args
        assert args[1] is None
        assert len(result["products"]) == 1

    @pytest.mark.asyncio
    @patch("services.search_service.get_products_meta")
    @patch("services.search_service.match_products")
    @patch("services.search_service.EmbeddingService")
    @patch("services.search_service.parse_query", new_callable=AsyncMock)
    async def test_missing_meta_skipped(
        self, mock_parse, mock_emb_cls, mock_match, mock_metas
    ):
        from services.search_service import run_search

        mock_parse.return_value = {"category": "base", "features": {}}
        emb = MagicMock()
        emb.embed.return_value = [0.1] * 1024
        mock_emb_cls.get.return_value = emb
        mock_match.return_value = [
            {"product_id": "p1", "similarity": 0.9},
            {"product_id": "ghost", "similarity": 0.8},
        ]
        mock_metas.return_value = {"p1": _meta("p1", "쿠션", "브랜드")}

        result = await run_search("쿠션")
        # 메타 없는 ghost는 제외
        assert len(result["products"]) == 1
        assert result["products"][0]["productId"] == "p1"