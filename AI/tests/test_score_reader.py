"""score_reader 단위 테스트. Supabase 호출 모킹."""
from unittest.mock import MagicMock, patch


class TestScoreReader:
    @patch("db.score_reader.get_supabase")
    def test_get_insights(self, mock_sb):
        from db.score_reader import get_insights

        sb = MagicMock()
        sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {
                "product_id": "p1",
                "lowest_price": 25000,
                "products": {"original_price": 30000},
            }
        ]
        mock_sb.return_value = sb
        out = get_insights(["p1"])
        assert out["p1"]["lowest_price"] == 25000
        assert out["p1"]["original_price"] == 30000

    @patch("db.score_reader.get_supabase")
    def test_get_features(self, mock_sb):
        from db.score_reader import get_features

        sb = MagicMock()
        sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {"product_id": "p1", "feature_json": {"skin_type": "지성"}}
        ]
        mock_sb.return_value = sb
        out = get_features(["p1"])
        assert out["p1"]["skin_type"] == "지성"

    def test_get_insights_empty(self):
        from db.score_reader import get_insights
        assert get_insights([]) == {}

    def test_get_features_empty(self):
        from db.score_reader import get_features
        assert get_features([]) == {}