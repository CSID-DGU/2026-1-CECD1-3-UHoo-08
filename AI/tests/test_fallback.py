from unittest.mock import patch

import pytest


class TestFallback:
    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.fallback.get_products_meta")
    @patch("agents.collaborative_agent.fallback.get_popular_products_by_skin_type")
    async def test_fallback_returns_popular(self, mock_pop, mock_metas):
        from agents.collaborative_agent.fallback import run_fallback

        mock_pop.return_value = ["p1", "p2"]
        mock_metas.return_value = {
            "p1": {"id": "p1", "name": "A", "brand": "B1", "category": "base", "image_url": None, "price": 20000},
            "p2": {"id": "p2", "name": "B", "brand": "B2", "category": "base", "image_url": None, "price": 25000},
        }
        results = await run_fallback("OILY", top_k=2)
        assert len(results) == 2
        assert results[0].id == "p1"

    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.fallback.get_products_meta")
    @patch("agents.collaborative_agent.fallback.get_popular_products_by_skin_type")
    async def test_exclude_ids_filtered(self, mock_pop, mock_metas):
        from agents.collaborative_agent.fallback import run_fallback

        mock_pop.return_value = ["p1", "p2", "p3"]
        mock_metas.return_value = {
            "p2": {"id": "p2", "name": "B", "brand": "B2", "category": "base", "image_url": None, "price": 25000},
            "p3": {"id": "p3", "name": "C", "brand": "B3", "category": "base", "image_url": None, "price": 30000},
        }
        results = await run_fallback("OILY", top_k=2, exclude_ids=["p1"])
        ids = [r.id for r in results]
        assert "p1" not in ids