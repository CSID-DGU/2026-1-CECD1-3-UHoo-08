"""price_value: 할인율 기반 가성비 점수."""
from typing import Optional


def compute(
    lowest_price: Optional[int],
    original_price: Optional[int],
) -> int:
    """
    할인율 = 1 - lowest/original.
    할인 0% → 50점, 50% 이상 → 100점, 그 사이 선형 매핑.
    데이터 없으면 50점 중립.
    """
    if lowest_price is None or original_price is None or original_price <= 0:
        return 50
    if lowest_price >= original_price:
        return 50  # 할인 없음

    discount_ratio = 1 - (lowest_price / original_price)  # 0.0 ~ 1.0
    # 0% → 50점, 50% 이상 → 100점
    if discount_ratio >= 0.5:
        return 100
    return int(50 + discount_ratio * 100)  # 0.0→50, 0.5→100