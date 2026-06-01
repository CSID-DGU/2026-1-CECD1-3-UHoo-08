"""
collaborative_agent의 콜드스타트 폴백.

집계 결과가 부족할 때(MIN_VALID_RESULTS 미만) 같은 skinType 사용자 전체의
인기 상품(평점 평균 기준)으로 대체. 본인 외 데이터가 충분하지 않은 신규 사용자
대응.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from db.product_reader import get_products_meta
from db.score_reader import get_popular_products_by_skin_type
from models.recommendation_result import SimilarUserProduct
from prompts.collaborative_strategy import FALLBACK_MIN_RATING


async def run_fallback(
    skin_type: Optional[str],
    top_k: int = 5,
    exclude_ids: Optional[List[str]] = None,
) -> List[SimilarUserProduct]:
    """
    같은 피부타입 인기 상품 top_k 반환. exclude_ids에 있는 상품은 제외.

    리뷰·평점이 부족하면 product_insights.average_score 기반 정렬로 폴백.
    """
    exclude_set = set(exclude_ids or [])

    # 여유분 확보 후 exclude 적용
    raw_ids = await asyncio.to_thread(
        get_popular_products_by_skin_type,
        skin_type,
        top_k + len(exclude_set),
        FALLBACK_MIN_RATING,
    )
    filtered_ids = [pid for pid in raw_ids if pid not in exclude_set][:top_k]
    if not filtered_ids:
        return []

    metas = await asyncio.to_thread(get_products_meta, filtered_ids)

    results: List[SimilarUserProduct] = []
    for pid in filtered_ids:
        meta = metas.get(pid)
        if meta is None:
            continue
        results.append(
            SimilarUserProduct(
                id=meta["id"],
                name=meta["name"],
                brand=meta["brand"],
                image_url=meta["image_url"],
                price=meta["price"],
                satisfaction_percent=70,  # 폴백 기본값
            )
        )
    return results