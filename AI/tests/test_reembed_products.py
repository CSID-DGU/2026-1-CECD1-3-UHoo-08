"""reembed_products 단위 테스트. Supabase·임베딩 모킹."""
from unittest.mock import MagicMock, patch


class TestReembedProducts:
    @patch("scripts.reembed_products.get_supabase")
    @patch("scripts.reembed_products.EmbeddingService")
    def test_reembed_basic_flow(self, mock_emb_cls, mock_get_sb):
        from scripts.reembed_products import reembed_products

        # products + product_features 조회 결과
        sb = MagicMock()
        sb.table.return_value.select.return_value.execute.return_value.data = [
            {
                "id": "p1",
                "category": "base",
                "product_features": {"feature_json": {"product_type": "쿠션", "coverage": "중간"}},
            },
            {
                "id": "p2",
                "category": "skincare",
                "product_features": [{"feature_json": {"product_type": "토너"}}],
            },
        ]
        mock_get_sb.return_value = sb

        emb = MagicMock()
        emb.embed_batch.return_value = [[0.1] * 1024, [0.2] * 1024]
        emb.model_version = "bge-m3-v1.5"
        mock_emb_cls.get.return_value = emb

        count = reembed_products(batch_size=8)
        assert count == 2
        # upsert 호출 확인
        sb.table.return_value.upsert.assert_called_once()

    @patch("scripts.reembed_products.get_supabase")
    @patch("scripts.reembed_products.EmbeddingService")
    def test_skips_products_without_features(self, mock_emb_cls, mock_get_sb):
        from scripts.reembed_products import reembed_products

        sb = MagicMock()
        sb.table.return_value.select.return_value.execute.return_value.data = [
            {"id": "p1", "category": "base", "product_features": None},
        ]
        mock_get_sb.return_value = sb
        mock_emb_cls.get.return_value = MagicMock()

        count = reembed_products()
        assert count == 0

    @patch("scripts.reembed_products.get_supabase")
    @patch("scripts.reembed_products.EmbeddingService")
    def test_skips_unknown_category(self, mock_emb_cls, mock_get_sb):
        from scripts.reembed_products import reembed_products

        sb = MagicMock()
        sb.table.return_value.select.return_value.execute.return_value.data = [
            {
                "id": "p1",
                "category": "unknown_cat",
                "product_features": {"feature_json": {"product_type": "x"}},
            },
        ]
        mock_get_sb.return_value = sb
        emb = MagicMock()
        mock_emb_cls.get.return_value = emb

        count = reembed_products()
        # 알 수 없는 카테고리는 건너뛰어 0건
        assert count == 0
        emb.embed_batch.assert_not_called()