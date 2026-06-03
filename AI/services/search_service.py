"""
검색창 자연어 검색 흐름.

intent 분류로 두 경로 분기:
- PRODUCT_NAME   : products.name/brand ILIKE 직접 조회 (벡터 연산 없음)
- RECOMMENDATION : 기존 추천 파이프라인 (query 파싱 → 자연어 → 임베딩 → pgvector)

추천 경로는 building block(query_parser, feature_text_builder,
embedding_service, match_products, product_reader)을 재사용하며,
RAG·score_agent 없이 경량으로 동작한다.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional, TypedDict

from db.product_reader import get_products_meta, search_products_by_name
from db.vector_search import match_products
from services.embedding_service import EmbeddingService
from services.feature_text_builder import build_product_text
from services.query_parser import classify_intent, parse_query


class SearchResultProduct(TypedDict):
    productId: str
    name: str
    brand: str
    category: str
    imageUrl: Optional[str]
    originalPrice: Optional[int]
    matchScore: int


class SearchResult(TypedDict):
    query: str
    intent: str # PRODUCT_NAME | RECOMMENDATION
    category: Optional[str]
    products: List[SearchResultProduct]


async def run_search(query: str, top_k: int = 20) -> SearchResult:
    """
    검색 핵심 로직.

    1. classify_intent: 쿼리 의도 분류
    2-A. PRODUCT_NAME    → search_products_by_name (ILIKE, 벡터 X)
    2-B. RECOMMENDATION  → parse → 자연어 → 임베딩 → match_products
    """
    if not query or not query.strip():
        return SearchResult(
            query=query, intent="RECOMMENDATION", category=None, products=[]
        )
    
    # 1. 의도 분류
    intent = await classify_intent(query)

    # 2-A. 상품명 직접 조회 (벡터 연산 없음)
    if intent == "PRODUCT_NAME":
        return await _search_by_name(query, top_k)

    # 2-B. 추천 파이프라인
    return await _search_by_recommendation(query, top_k)


async def _search_by_name(query: str, top_k: int) -> SearchResult:
    """상품명·브랜드 ILIKE 직접 조회. matchScore는 100 고정(정확 매칭 의미)."""
    metas = await asyncio.to_thread(search_products_by_name, query, top_k)
    products: List[SearchResultProduct] = [
        SearchResultProduct(
            productId=m["id"],
            name=m["name"],
            brand=m["brand"],
            category=m["category"],
            imageUrl=m["image_url"],
            originalPrice=m["price"],
            matchScore=100,
        )
        for m in metas
    ]
    # 상품명 검색은 카테고리 개념이 약하므로 None
    return SearchResult(
        query=query, intent="PRODUCT_NAME", category=None, products=products
    )


async def _search_by_recommendation(query: str, top_k: int) -> SearchResult:
    """
    2-B. (RECOMMENDATION) 흐름:
      1. query_parser: 쿼리 → category + features
      2. feature_text_builder: features → 자연어 (실패 시 원본 쿼리)
      3. embedding_service: 자연어 → query_vector
      4. match_products: query_vector로 후보 검색 (제외 없음)
      5. product_reader: 메타 조인 + matchScore(=similarity X 100)
    """

    # 1. 쿼리 파싱
    parsed = await parse_query(query)
    category = parsed["category"]
    features = parsed["features"]

    # 2. feature → 자연어. 원본 쿼리를 항상 결합해 의미 손실 방지
    feature_text = ""
    if category and features:
        try:
            feature_text = build_product_text(category, features)
        except Exception:
            feature_text = ""
    search_text = f"{query}. {feature_text}".strip() if feature_text else query

    # 3. 임베딩
    emb = EmbeddingService.get()
    query_vector = await asyncio.to_thread(emb.embed, search_text)

    # 4. 후보 검색 (base_product 없으니 exclude 빈 리스트)
    matches = await asyncio.to_thread(
        match_products, query_vector, category, top_k, []
    )
    if not matches:
        return SearchResult(
            query=query, intent="RECOMMENDATION", category=category, products=[]
        )

    # 5. 메타 조인 + matchScore
    product_ids = [m["product_id"] for m in matches]
    metas = await asyncio.to_thread(get_products_meta, product_ids)

    products: List[SearchResultProduct] = []
    for m in matches:
        meta = metas.get(m["product_id"])
        if meta is None:
            continue
        sim = max(0.0, min(1.0, m["similarity"]))
        products.append(
            SearchResultProduct(
                productId=meta["id"],
                name=meta["name"],
                brand=meta["brand"],
                category=meta["category"],
                imageUrl=meta["image_url"],
                originalPrice=meta["price"],
                matchScore=round(sim * 100),
            )
        )

    return SearchResult(
        query=query, intent="RECOMMENDATION", category=category, products=products
    )
