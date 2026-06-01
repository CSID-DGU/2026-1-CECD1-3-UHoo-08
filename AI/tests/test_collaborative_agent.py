from unittest.mock import AsyncMock, patch

import pytest


class TestCollaborativeAgent:
    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.run_fallback", new_callable=AsyncMock)
    @patch("agents.collaborative_agent.get_products_meta")
    @patch("agents.collaborative_agent.get_user_products_by_users")
    @patch("agents.collaborative_agent.get_similar_user_ids")
    async def test_aggregation_path(
        self, mock_sim, mock_ups, mock_metas, mock_fallback
    ):
        from agents.collaborative_agent import run_collaborative

        mock_sim.return_value = ["u2", "u3", "u4"]
        mock_ups.return_value = [
            {"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": 5},
            {"user_id": "u3", "product_id": "p1", "usage_type": "USED", "rating": 4},
            {"user_id": "u4", "product_id": "p1", "usage_type": "USING", "rating": 5},
            {"user_id": "u2", "product_id": "p2", "usage_type": "INTERESTED", "rating": 3},
            {"user_id": "u3", "product_id": "p2", "usage_type": "USED", "rating": 4},
            {"user_id": "u4", "product_id": "p3", "usage_type": "USING", "rating": 4},
        ]
        mock_metas.return_value = {
            "p1": {"id": "p1", "name": "쿠션A", "brand": "B1", "category": "base", "image_url": None, "price": 30000},
            "p2": {"id": "p2", "name": "쿠션B", "brand": "B2", "category": "base", "image_url": None, "price": 25000},
            "p3": {"id": "p3", "name": "쿠션C", "brand": "B3", "category": "base", "image_url": None, "price": 35000},
        }

        results = await run_collaborative(
            user_id="u1",
            skin_type="OILY",
            personal_color="SPRING_WARM",
            top_k=3,
        )
        # 폴백 안 거침
        mock_fallback.assert_not_called()
        # weighted_score 1위 → p1
        assert results[0].id == "p1"
        assert len(results) == 3

    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.run_fallback", new_callable=AsyncMock)
    @patch("agents.collaborative_agent.get_similar_user_ids")
    async def test_no_similar_users_goes_to_fallback(self, mock_sim, mock_fallback):
        from agents.collaborative_agent import run_collaborative

        mock_sim.return_value = []
        mock_fallback.return_value = []

        await run_collaborative(
            user_id="u1",
            skin_type="OILY",
            personal_color="SPRING_WARM",
        )
        mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.run_fallback", new_callable=AsyncMock)
    @patch("agents.collaborative_agent.get_user_products_by_users")
    @patch("agents.collaborative_agent.get_similar_user_ids")
    async def test_insufficient_results_goes_to_fallback(
        self, mock_sim, mock_ups, mock_fallback
    ):
        from agents.collaborative_agent import run_collaborative

        mock_sim.return_value = ["u2"]
        mock_ups.return_value = [
            {"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": 5},
        ]  # MIN_VALID_RESULTS=3 미만
        mock_fallback.return_value = []

        await run_collaborative(user_id="u1", skin_type="OILY", personal_color=None)
        mock_fallback.assert_called_once()

    @pytest.mark.asyncio
    @patch("agents.collaborative_agent.get_products_meta")
    @patch("agents.collaborative_agent.get_user_products_by_users")
    @patch("agents.collaborative_agent.get_similar_user_ids")
    async def test_exclude_ids_filtered(self, mock_sim, mock_ups, mock_metas):
        from agents.collaborative_agent import run_collaborative

        mock_sim.return_value = ["u2", "u3", "u4"]
        mock_ups.return_value = [
            {"user_id": "u2", "product_id": "p1", "usage_type": "USING", "rating": 5},
            {"user_id": "u3", "product_id": "p2", "usage_type": "USING", "rating": 4},
            {"user_id": "u4", "product_id": "p3", "usage_type": "USING", "rating": 4},
        ]
        mock_metas.return_value = {
            "p2": {"id": "p2", "name": "쿠션B", "brand": "B2", "category": "base", "image_url": None, "price": 25000},
            "p3": {"id": "p3", "name": "쿠션C", "brand": "B3", "category": "base", "image_url": None, "price": 35000},
        }

        results = await run_collaborative(
            user_id="u1",
            skin_type="OILY",
            personal_color="SPRING_WARM",
            exclude_ids=["p1"],
            top_k=3,
        )
        assert all(r.id != "p1" for r in results)