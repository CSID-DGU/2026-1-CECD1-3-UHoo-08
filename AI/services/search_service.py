"""
자연어 검색 오케스트레이션.

query → query_parser(Qwen) → category + features
      → feature_text_builder → 자연어 문자열
      → embedding_service(bge-m3) → query_vector
      → match_products(pgvector) → 후보
      → product_reader → 메타 조인 + matchScore(similarity×100)
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from db.product_reader import get_products_meta
from db.vector_search import match_products
from services.embedding_service import EmbeddingService
from services.feature_text_builder import build_product_text
from services.query_parser import parse_query


async def search(query: str, top_k: int = 20) -> Dict[str, Any]:
    """자연어 검색 전체 파이프라인. FE 계약 포맷 딕셔너리 반환."""
    parsed = await parse_query(query)
    category: str = parsed.get("category") or "base"
    features: Dict[str, Any] = parsed.get("features") or {}

    try:
        feature_text = build_product_text(category, features)
    except ValueError:
        feature_text = ""

    # feature_text가 비어 있으면 원문 쿼리로 fallback
    embed_input = feature_text.strip() or query

    emb = EmbeddingService.get()
    query_vector: List[float] = await asyncio.to_thread(emb.embed, embed_input)

    matches = match_products(query_vector, category=category, match_count=top_k)

    product_ids = [m["product_id"] for m in matches]
    meta_map = get_products_meta(product_ids)

    products = []
    for m in matches:
        pid = m["product_id"]
        meta = meta_map.get(pid)
        if not meta:
            continue
        products.append(
            {
                "productId": pid,
                "name": meta["name"],
                "brand": meta["brand"],
                "category": meta["category"],
                "imageUrl": meta.get("image_url"),
                "originalPrice": meta.get("price"),
                "matchScore": round(m["similarity"] * 100),
            }
        )

    return {"query": query, "category": category, "products": products}
