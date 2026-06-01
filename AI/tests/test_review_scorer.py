from unittest.mock import patch

from agents.score_agent import review_scorer


class TestReviewScorer:
    @patch("agents.score_agent.review_scorer.match_reviews")
    def test_average_similarity_converted(self, mock_mr):
        mock_mr.return_value = [
            {"review_id": "r1", "review_text": "t1", "similarity": 0.9},
            {"review_id": "r2", "review_text": "t2", "similarity": 0.8},
        ]
        # 평균 0.85 → 85점
        assert review_scorer.compute([0.1] * 1024, "p1", 10) == 85

    @patch("agents.score_agent.review_scorer.match_reviews")
    def test_no_reviews_returns_neutral(self, mock_mr):
        mock_mr.return_value = []
        assert review_scorer.compute([0.1] * 1024, "p1", 10) == 50

    @patch("agents.score_agent.review_scorer.match_reviews")
    def test_clamp_above_one(self, mock_mr):
        # 부정확한 RPC 값 방어
        mock_mr.return_value = [{"review_id": "r", "review_text": "t", "similarity": 1.2}]
        assert review_scorer.compute([0.1] * 1024, "p1", 10) == 100

    @patch("agents.score_agent.review_scorer.match_reviews")
    def test_clamp_below_zero(self, mock_mr):
        mock_mr.return_value = [{"review_id": "r", "review_text": "t", "similarity": -0.2}]
        assert review_scorer.compute([0.1] * 1024, "p1", 10) == 0