"""seed-reviews 라우터 테스트. collect_reviews·reembed_reviews 모킹."""
from unittest.mock import patch

from fastapi.testclient import TestClient


def _client():
    from app.main import app
    return TestClient(app)


class TestSeedReviewsRouter:
    @patch("api.internal.review_admin_router.collect_reviews")
    def test_without_auto_embed(self, mock_collect):
        mock_collect.return_value = {
            "category": "base",
            "saved": 5,
            "skipped": 0,
            "errors": [],
            "results": [],
        }
        client = _client()
        resp = client.post(
            "/internal/admin/seed-reviews",
            json={"category": "base", "limit": 5, "per_product": 8},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["saved"] == 5
        # auto_embed 기본 False → embedded 0
        assert data["embedded"] == 0

    @patch("scripts.reembed_reviews.reembed_reviews")
    @patch("api.internal.review_admin_router.collect_reviews")
    def test_with_auto_embed(self, mock_collect, mock_reembed):
        mock_collect.return_value = {
            "category": "base",
            "saved": 5,
            "skipped": 0,
            "errors": [],
            "results": [],
        }
        mock_reembed.return_value = 12  # 청크 분할로 5개 리뷰 → 12청크 가정

        client = _client()
        resp = client.post(
            "/internal/admin/seed-reviews",
            json={"category": "base", "limit": 5, "per_product": 8, "auto_embed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["saved"] == 5
        assert data["embedded"] == 12
        mock_reembed.assert_called_once()

    @patch("scripts.reembed_reviews.reembed_reviews")
    @patch("api.internal.review_admin_router.collect_reviews")
    def test_auto_embed_skipped_when_no_reviews(self, mock_collect, mock_reembed):
        # 수집 0건이면 auto_embed=True여도 임베딩 안 함
        mock_collect.return_value = {
            "category": "base",
            "saved": 0,
            "skipped": 3,
            "errors": [],
            "results": [],
        }
        client = _client()
        resp = client.post(
            "/internal/admin/seed-reviews",
            json={"category": "base", "auto_embed": True},
        )
        assert resp.status_code == 200
        assert resp.json()["embedded"] == 0
        mock_reembed.assert_not_called()

    @patch("scripts.reembed_reviews.reembed_reviews")
    @patch("api.internal.review_admin_router.collect_reviews")
    def test_embed_failure_keeps_collect_result(self, mock_collect, mock_reembed):
        # 임베딩 실패해도 수집 결과는 살아있어야 함
        mock_collect.return_value = {
            "category": "base",
            "saved": 5,
            "skipped": 0,
            "errors": [],
            "results": [],
        }
        mock_reembed.side_effect = RuntimeError("bge-m3 로딩 실패")

        client = _client()
        resp = client.post(
            "/internal/admin/seed-reviews",
            json={"category": "base", "auto_embed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["saved"] == 5          # 수집 결과 유지
        assert data["embedded"] == 0
        # reembed 에러가 errors에 기록됨
        assert any(e.get("stage") == "reembed" for e in data["errors"])