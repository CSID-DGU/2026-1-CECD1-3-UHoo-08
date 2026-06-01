"""
상품 재임베딩 스크립트.

products + product_features를 조회해 카테고리별 자연어로 변환하고,
bge-m3로 배치 임베딩하여 product_embeddings에 upsert한다.

사용법:
    cd AI
    python -m scripts.reembed_products              # 전체 재임베딩
    python -m scripts.reembed_products --batch 16   # 배치 크기 지정

전제: products, product_features에 원본 데이터가 있어야 한다.
"""
from __future__ import annotations

import argparse
from typing import Any, Dict, List

from db.supabase_client import get_supabase
from services.embedding_service import EmbeddingService
from services.feature_text_builder import build_product_text


def _fetch_products_with_features() -> List[Dict[str, Any]]:
    """
    products와 product_features를 조인 조회.

    product_features가 있는 상품만 임베딩 대상 (feature_json 없으면 자연어 변환 불가).
    """
    sb = get_supabase()
    res = (
        sb.table("products")
        .select("id, category, product_features(feature_json)")
        .execute()
    )
    rows = []
    for p in res.data or []:
        pf = p.get("product_features")
        # product_features는 1:1이라 dict 또는 list로 올 수 있음
        if isinstance(pf, list):
            pf = pf[0] if pf else None
        if not pf or not pf.get("feature_json"):
            continue
        rows.append(
            {
                "product_id": p["id"],
                "category": p["category"],
                "feature_json": pf["feature_json"],
            }
        )
    return rows


def reembed_products(batch_size: int = 32) -> int:
    """
    전체 상품 재임베딩 후 upsert. 적재된 행 수 반환.
    """
    rows = _fetch_products_with_features()
    if not rows:
        print("임베딩할 상품이 없습니다. products·product_features를 먼저 채우세요.")
        return 0

    emb = EmbeddingService.get()

    # 1. 자연어 변환 (알 수 없는 카테고리는 건너뜀)
    valid: List[Dict[str, Any]] = []
    texts: List[str] = []
    for r in rows:
        try:
            text = build_product_text(r["category"], r["feature_json"])
        except ValueError:
            print(f"[skip] 알 수 없는 카테고리: {r['category']} (product {r['product_id']})")
            continue
        if not text:
            continue
        valid.append(r)
        texts.append(text)

    if not texts:
        print("자연어 변환 결과가 모두 비어있습니다.")
        return 0

    # 2. 배치 임베딩
    vecs = emb.embed_batch(texts, batch_size=batch_size)

    # 3. upsert payload
    payload = [
        {
            "product_id": r["product_id"],
            "feature_vec": v,
            "model_version": emb.model_version,
        }
        for r, v in zip(valid, vecs)
    ]

    sb = get_supabase()
    sb.table("product_embeddings").upsert(
        payload, on_conflict="product_id"
    ).execute()
    print(f"product_embeddings에 {len(payload)}건 upsert 완료")
    return len(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="상품 재임베딩")
    parser.add_argument("--batch", type=int, default=32, help="임베딩 배치 크기")
    args = parser.parse_args()
    reembed_products(batch_size=args.batch)


if __name__ == "__main__":
    main()