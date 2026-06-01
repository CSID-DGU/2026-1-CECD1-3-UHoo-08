"""product_reader read-only 조회 테스트. Supabase 호출은 모킹."""
from unittest.mock import MagicMock, patch

import pytest

from db.product_reader import (
    get_product_meta,
    get_product_meta_with_vec,
    get_products_meta,
)


def _row(pid="p1", name="네오쿠션", brand="LANEIGE"):
    return {
        "product_id": pid,
        "name": name,
        "brand": brand,
        "category": "base",
        "image_url": "https://img/x.jpg",
        "original_price": 30000,
    }


class TestProductReader:
    @patch("db.product_reader.get_supabase")
    def test_get_product_meta_found(self, mock_get_sb):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [_row()]
        mock_get_sb.return_value = sb

        meta = get_product_meta("p1")
        assert meta is not None
        assert meta["id"] == "p1"
        assert meta["name"] == "네오쿠션"
        assert meta["price"] == 30000

    @patch("db.product_reader.get_supabase")
    def test_get_product_meta_not_found(self, mock_get_sb):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        mock_get_sb.return_value = sb

        assert get_product_meta("nope") is None

    @patch("db.product_reader.get_supabase")
    def test_get_product_meta_with_vec_success(self, mock_get_sb):
        """products + product_embeddings 정상 조회 시 feature_vec 포함."""
        sb = MagicMock()
        # products 조회 결과
        products_res = MagicMock()
        products_res.data = [{
            "product_id": "p1", "name": "네오쿠션", "brand": "LANEIGE",
            "category": "base", "image_url": None, "original_price": 30000,
        }]
        # product_embeddings 조회 결과
        emb_res = MagicMock()
        emb_res.data = [{"feature_vec": [0.1] * 1024}]

        # 두 번의 .execute() 호출에 순서대로 응답
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.side_effect = [
            products_res, emb_res,
        ]
        mock_get_sb.return_value = sb

        meta = get_product_meta_with_vec("p1")
        assert meta["id"] == "p1"
        assert meta["feature_vec"] == [0.1] * 1024

    @patch("db.product_reader.get_supabase")
    def test_get_product_meta_with_vec_product_not_found(self, mock_get_sb):
        """상품 자체가 없으면 None."""
        sb = MagicMock()
        products_res = MagicMock()
        products_res.data = []
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = products_res
        mock_get_sb.return_value = sb

        assert get_product_meta_with_vec("nope") is None

    @patch("db.product_reader.get_supabase")
    def test_get_product_meta_with_vec_no_feature_vec_raises(self, mock_get_sb):
        """상품은 있으나 feature_vec 미생성이면 ValueError."""
        sb = MagicMock()
        products_res = MagicMock()
        products_res.data = [{
            "product_id": "p1", "name": "네오쿠션", "brand": "LANEIGE",
            "category": "base", "image_url": None, "original_price": 30000,
        }]
        emb_res = MagicMock()
        emb_res.data = []  # feature_vec 없음
        sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.side_effect = [
            products_res, emb_res,
        ]
        mock_get_sb.return_value = sb

        with pytest.raises(ValueError):
            get_product_meta_with_vec("p1")

    @patch("db.product_reader.get_supabase")
    def test_get_products_meta_batch(self, mock_get_sb):
        sb = MagicMock()
        sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            _row("p1", "쿠션A", "브랜드A"),
            _row("p2", "쿠션B", "브랜드B"),
        ]
        mock_get_sb.return_value = sb

        metas = get_products_meta(["p1", "p2"])
        assert set(metas.keys()) == {"p1", "p2"}
        assert metas["p1"]["name"] == "쿠션A"

    def test_get_products_meta_empty_input(self):
        # 빈 입력은 DB 호출 없이 빈 딕셔너리
        assert get_products_meta([]) == {}