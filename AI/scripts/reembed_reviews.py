"""
리뷰 재임베딩 스크립트.

리뷰 원본을 청크 분할·임베딩하여 review_embeddings에 적재한다.
동일 리뷰 청크 중복 적재를 피하기 위해 (product_id, 텍스트 해시) 기준으로 중복 확인.

사용법:
    cd AI
    python -m scripts.reembed_reviews
    python -m scripts.reembed_reviews --batch 16

전제: 리뷰 원본 테이블(reviews)에 데이터가 있어야 한다.
"""
from __future__ import annotations

import argparse
import hashlib
from typing import Any, Dict, List

from db.supabase_client import get_supabase
from services.embedding_service import EmbeddingService
from services.review_chunker import chunk_review


def _text_hash(product_id: str, text: str) -> str:
    """중복 회피용 해시. product_id + 청크 텍스트."""
    return hashlib.sha256(f"{product_id}::{text}".encode("utf-8")).hexdigest()


def _fetch_reviews() -> List[Dict[str, Any]]:
    """reviews 테이블에서 원본 리뷰 조회. review_embeddings의 단일 소스."""
    sb = get_supabase()
    try:
        res = sb.table("reviews").select("product_id, content, source").execute()
        return res.data or []
    except Exception as e:
        print(f"reviews 조회 실패 (테이블 미존재 가능): {e}")
        return []


def _existing_hashes() -> set:
    """이미 적재된 review_embeddings의 텍스트 해시 집합. (review_text로 재계산)"""
    sb = get_supabase()
    res = sb.table("review_embeddings").select("product_id, review_text").execute()
    return {
        _text_hash(row["product_id"], row["review_text"])
        for row in (res.data or [])
    }


def reembed_reviews(batch_size: int = 32) -> int:
    """리뷰 청크 임베딩 후 INSERT. 적재 건수 반환."""
    raw = _fetch_reviews()
    if not raw:
        print("임베딩할 리뷰가 없습니다.")
        return 0

    existing = _existing_hashes()
    emb = EmbeddingService.get()

    # 1. 청크 분할 + 중복 제거
    pending: List[Dict[str, str]] = []
    for r in raw:
        product_id = r["product_id"]
        source = r.get("source", "UNKNOWN")
        for chunk in chunk_review(r.get("content", "")):
            h = _text_hash(product_id, chunk)
            if h in existing:
                continue
            existing.add(h)  # 같은 실행 내 중복도 방지
            pending.append(
                {"product_id": product_id, "review_text": chunk, "source": source}
            )

    if not pending:
        print("새로 적재할 리뷰 청크가 없습니다 (전부 중복).")
        return 0

    # 2. 배치 임베딩
    texts = [p["review_text"] for p in pending]
    vecs = emb.embed_batch(texts, batch_size=batch_size)

    # 3. INSERT
    payload = [
        {
            "product_id": p["product_id"],
            "review_text": p["review_text"],
            "embedding": v,
            "source": p["source"],
        }
        for p, v in zip(pending, vecs)
    ]
    sb = get_supabase()
    sb.table("review_embeddings").insert(payload).execute()
    print(f"review_embeddings에 {len(payload)}건 insert 완료")
    return len(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="리뷰 재임베딩")
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()
    reembed_reviews(batch_size=args.batch)


if __name__ == "__main__":
    main()