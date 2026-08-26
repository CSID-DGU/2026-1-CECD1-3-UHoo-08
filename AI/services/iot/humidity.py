"""
습도 환산.

상대습도(%RH)는 그 자체로 공기가 머금은 물의 양을 뜻하지 않는다.
같은 50%RH라도 30℃ 공기는 15.2 g/m³, 15℃ 공기는 6.4 g/m³를 담는다.
"겨울 실내가 왜 건조한가"를 설명하려면 절대습도로 바꿔야 한다.

    es(T) = 6.112 × exp(17.67·T / (T + 243.5))          [hPa]   Magnus 식
    AH    = 2.1674 × es(T) × RH / (273.15 + T)          [g/m³]

RH는 백분율(0~100)을 그대로 넣는다.
"""
from __future__ import annotations

import math

from typing import Optional

# Magnus 식 계수 (물 표면 기준, -40 ~ +50℃ 구간에서 오차 0.4% 이내)
_MAGNUS_A = 6.112
_MAGNUS_B = 17.67
_MAGNUS_C = 243.5

# hPa·%RH/K → g/m³ 환산 계수. 이 값에 백분율 RH 입력이 전제되어 있다.
_AH_COEF = 2.1674

# 실내 건조 판단 기준 (설계서 §6). 절대습도가 이 아래면 건조로 본다.
DRY_THRESHOLD_GM3 = 7.0


def saturation_vapor_pressure(temp_c: float) -> float:
    """포화수증기압 [hPa]. 그 온도의 공기가 담을 수 있는 물의 최대치."""
    return _MAGNUS_A * math.exp(_MAGNUS_B * temp_c / (temp_c + _MAGNUS_C))


def absolute_humidity(
    temp_c: Optional[float],
    rh_pct: Optional[float],
) -> Optional[float]:
    """
    절대습도 [g/m³]. 온도나 습도가 없으면 None.

        25℃ 50%RH → 11.5
        22℃ 31%RH →  5.9   (건조)
        30℃ 70%RH → 21.3
    """
    if temp_c is None or rh_pct is None:
        return None
    es = saturation_vapor_pressure(float(temp_c))
    return _AH_COEF * es * float(rh_pct) / (273.15 + float(temp_c))


def is_dry(ah_gm3: Optional[float], *, threshold: float = DRY_THRESHOLD_GM3) -> Optional[bool]:
    """건조 여부. 값이 없으면 None(모름)이며 False로 뭉개지 않는다."""
    if ah_gm3 is None:
        return None
    return ah_gm3 < threshold


if __name__ == "__main__":
    print("  T(℃)  RH(%)   es(hPa)   AH(g/m³)")
    for t, rh in [(30, 50), (15, 50), (25, 50), (22, 31), (24.1, 47),
                  (26.8, 52), (30, 70), (5, 60)]:
        ah = absolute_humidity(t, rh)
        print(f"  {t:>5}  {rh:>5}   {saturation_vapor_pressure(t):>7.2f}   "
              f"{ah:>7.2f}{'  ← 건조' if is_dry(ah) else ''}")