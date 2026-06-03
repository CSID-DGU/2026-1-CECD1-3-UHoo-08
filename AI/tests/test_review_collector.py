"""review_collector 단위 테스트. Gemini·Supabase 모킹."""
from unittest.mock import MagicMock, patch


class TestReviewCollector:
    @patch("services.review_collector.get_supabase")
    @patch("services.review_collector.genai")
    def test_basic_flow(self, mock_genai, mock_get_sb):
        from services.review_collector import collect_reviews

        sb = MagicMock()
        # _fetch_products
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"product_id": "p1", "name": "네오쿠션", "brand": "LANEIGE"},
        ]
        mock_get_sb.return_value = sb

        client = MagicMock()
        client.models.generate_content.return_value = MagicMock(
            text='{"reviews": [{"content": "지성 피부에 잘 맞아요.", "rating": 5}, '
                 '{"content": "약간 건조해요.", "rating": 3}]}'
        )
        mock_genai.Client.return_value = client

        result = collect_reviews("base", limit=10, per_product=2)
        assert result["saved"] == 2
        assert result["category"] == "base"

    @patch("services.review_collector.get_supabase")
    @patch("services.review_collector.genai")
    def test_no_products(self, mock_genai, mock_get_sb):
        from services.review_collector import collect_reviews

        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_get_sb.return_value = sb

        result = collect_reviews("base")
        assert result["saved"] == 0
        mock_genai.Client.assert_not_called()

    @patch("services.review_collector.get_supabase")
    @patch("services.review_collector.genai")
    def test_no_reviews_found_skipped(self, mock_genai, mock_get_sb):
        from services.review_collector import collect_reviews

        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"product_id": "p1", "name": "x", "brand": "y"},
        ]
        mock_get_sb.return_value = sb

        client = MagicMock()
        client.models.generate_content.return_value = MagicMock(text='{"reviews": []}')
        mock_genai.Client.return_value = client

        result = collect_reviews("base")
        assert result["saved"] == 0
        assert result["skipped"] == 1

    @patch("services.review_collector.get_supabase")
    @patch("services.review_collector.genai")
    def test_invalid_category(self, mock_genai, mock_get_sb):
        from services.review_collector import collect_reviews
        import pytest

        with pytest.raises(ValueError):
            collect_reviews("makeup")

    @patch("services.review_collector.get_supabase")
    @patch("services.review_collector.genai")
    def test_json_parse_failure(self, mock_genai, mock_get_sb):
        from services.review_collector import collect_reviews

        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"product_id": "p1", "name": "쿠션", "brand": "B"},
        ]
        mock_get_sb.return_value = sb

        client = MagicMock()
        client.models.generate_content.return_value = MagicMock(text="이건 JSON 아님")
        mock_genai.Client.return_value = client

        result = collect_reviews("base")
        # 파싱 실패 → 저장 0, skipped
        assert result["saved"] == 0