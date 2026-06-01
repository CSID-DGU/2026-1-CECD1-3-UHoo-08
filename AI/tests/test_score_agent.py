from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestScoreAgent:
    @pytest.mark.asyncio
    @patch("agents.score_agent.review_scorer.match_reviews")
    @patch("agents.score_agent.get_qwen_llm")
    @patch("agents.score_agent.get_features")
    @patch("agents.score_agent.get_insights")
    async def test_run_score_full_flow(
        self, mock_ins, mock_feat, mock_qwen, mock_match_reviews
    ):
        from agents.score_agent import run_score

        mock_ins.return_value = {
            "p1": {"product_id": "p1", "lowest_price": 30000, "original_price": 40000},
            "p2": {"product_id": "p2", "lowest_price": 50000, "original_price": 50000},
        }
        mock_feat.return_value = {
            "p1": {"skin_type": "지성", "skin_concern": ["모공"]},
            "p2": {"skin_type": "건성"},
        }
        mock_match_reviews.return_value = [
            {"review_id": "r", "review_text": "t", "similarity": 0.9}
        ]
        llm = AsyncMock()
        llm.chat_json.return_value = {
            "budget_fit": 0.25,
            "price_value": 0.25,
            "review_score": 0.25,
            "personalization": 0.25,
        }
        mock_qwen.return_value = llm

        results = await run_score(
            intent_vector=[0.1] * 1024,
            candidate_ids=["p1", "p2"],
            user_profile={
                "skin_type": "OILY",
                "personal_color": None,
                "skin_concerns": ["SEBUM"],
            },
            search_purpose="DAILY",
            price_tolerance_percent=10,
            target_price=30000,
        )
        assert len(results) == 2
        # totalScore 내림차순
        assert results[0]["totalScore"] >= results[1]["totalScore"]
        # p1이 모든 면에서 유리하므로 1위
        assert results[0]["productId"] == "p1"

    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        from agents.score_agent import run_score

        results = await run_score(
            intent_vector=[0.1] * 1024,
            candidate_ids=[],
            user_profile={"skin_type": None, "personal_color": None, "skin_concerns": []},
        )
        assert results == []

    @pytest.mark.asyncio
    @patch("agents.score_agent.review_scorer.match_reviews")
    @patch("agents.score_agent.get_qwen_llm")
    @patch("agents.score_agent.get_features")
    @patch("agents.score_agent.get_insights")
    async def test_llm_failure_uses_default_weights(
        self, mock_ins, mock_feat, mock_qwen, mock_match_reviews
    ):
        from agents.score_agent import run_score

        mock_ins.return_value = {}
        mock_feat.return_value = {}
        mock_match_reviews.return_value = []
        llm = AsyncMock()
        llm.chat_json.return_value = None  # LLM 실패
        mock_qwen.return_value = llm

        results = await run_score(
            intent_vector=[0.1] * 1024,
            candidate_ids=["p1"],
            user_profile={"skin_type": None, "personal_color": None, "skin_concerns": []},
        )
        # 실패해도 점수 계산 진행
        assert len(results) == 1
        assert "totalScore" in results[0]