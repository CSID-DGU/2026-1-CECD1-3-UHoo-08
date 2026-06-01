"""recall_at_k 평가 로직 테스트. match_alternatives 모킹."""
from unittest.mock import patch


class TestRecallAtK:
    @patch("tests.eval.recall_at_k.load_dataset")
    @patch("tests.eval.recall_at_k.match_alternatives")
    def test_perfect_recall(self, mock_match, mock_load):
        from tests.eval.recall_at_k import evaluate

        mock_load.return_value = [
            {"base_product_id": "b1", "ground_truth": {"a1", "a2"}},
        ]
        # 정답 2개가 모두 상위에 등장
        mock_match.return_value = [
            {"product_id": "a1", "similarity": 0.9},
            {"product_id": "a2", "similarity": 0.85},
            {"product_id": "x", "similarity": 0.7},
        ]
        m = evaluate(k=10)
        assert m["recall@k"] == 1.0
        assert m["mrr"] == 1.0  # 첫 결과가 정답
        assert m["n_cases"] == 1

    @patch("tests.eval.recall_at_k.load_dataset")
    @patch("tests.eval.recall_at_k.match_alternatives")
    def test_partial_recall(self, mock_match, mock_load):
        from tests.eval.recall_at_k import evaluate

        mock_load.return_value = [
            {"base_product_id": "b1", "ground_truth": {"a1", "a2"}},
        ]
        # 2개 중 1개만 맞춤, 정답이 2번째
        mock_match.return_value = [
            {"product_id": "x", "similarity": 0.9},
            {"product_id": "a1", "similarity": 0.8},
        ]
        m = evaluate(k=10)
        assert m["recall@k"] == 0.5
        assert m["mrr"] == 0.5  # 2번째에 정답 → 1/2

    @patch("tests.eval.recall_at_k.load_dataset")
    @patch("tests.eval.recall_at_k.match_alternatives")
    def test_no_hit(self, mock_match, mock_load):
        from tests.eval.recall_at_k import evaluate

        mock_load.return_value = [
            {"base_product_id": "b1", "ground_truth": {"a1"}},
        ]
        mock_match.return_value = [
            {"product_id": "x", "similarity": 0.9},
            {"product_id": "y", "similarity": 0.8},
        ]
        m = evaluate(k=10)
        assert m["recall@k"] == 0.0
        assert m["mrr"] == 0.0

    @patch("tests.eval.recall_at_k.load_dataset")
    def test_empty_dataset(self, mock_load):
        from tests.eval.recall_at_k import evaluate

        mock_load.return_value = []
        m = evaluate(k=10)
        assert m["n_cases"] == 0
        assert m["recall@k"] == 0.0