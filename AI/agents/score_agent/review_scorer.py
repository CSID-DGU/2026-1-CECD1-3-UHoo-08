"""review_score: intent_vector vs review_embedding 코사인 유사도 평균."""
from typing import List

from db.vector_search import match_reviews


def compute(
    intent_vector: List[float],
    product_id: str,
    top_n: int = 10,
) -> int:
    """
    상품의 리뷰 중 intent_vector와 가장 가까운 N개의 유사도 평균 X 100.
    리뷰 없으면 50점 중립 (페널티 회피).
    """
    matches = match_reviews(intent_vector, product_id, top_n)
    if not matches:
        return 50
    avg = sum(m["similarity"] for m in matches) / len(matches)
    # 유사도 [0, 1] 클램프 후 0~100 변환
    avg_clamped = max(0.0, min(1.0, avg))
    return round(avg_clamped * 100)