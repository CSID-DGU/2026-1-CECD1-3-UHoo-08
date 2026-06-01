"""budget_fit: targetPrice 허용 폭에 들어오는지를 0~100점으로."""
from typing import Optional


def compute(
    lowest_price: Optional[int],
    target_price: Optional[int],
    tolerance_percent: Optional[int],
) -> int:
    """
    target_price 기준 ±tolerance_percent% 범위 안이면 100점.
    범위 밖이면 거리에 따라 선형 감점, 2배 벗어나면 0점.

    target_price 없으면 → 50점 중립
    lowest_price 없으면 50점 중립
    tolerance_percent None(상관없음) → 100점
    """
    if lowest_price is None or target_price is None:
        return 50
    if tolerance_percent is None:
        return 100
    if target_price <= 0:
        return 50

    diff_ratio = abs(lowest_price - target_price) / target_price * 100  # %
    tol = max(tolerance_percent, 1)

    if diff_ratio <= tol:
        return 100
    if diff_ratio >= tol * 2:
        return 0
    # tol < diff_ratio < 2*tol → 100~0 선형
    return int(100 * (1 - (diff_ratio - tol) / tol))