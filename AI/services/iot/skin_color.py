"""
AS7341 채널 → CIE L*a*b* 변환.

── 왜 Lab이어야 하는가 ─────────────────────────────────────────────
화장품 쪽(services/iot/optical)은 채널값의 상대 변화만 보면 됐다. "처음 잰
색과 몇 % 다른가"가 전부라 색 공간으로 옮길 이유가 없었다.

피부는 다르다. 우리가 보여주는 ITA°와 홍반 지수는 피부과학에서 쓰는 지표이고,
둘 다 L*·a*·b*로 정의되어 있다. 채널값 그대로는 그 식에 넣을 수 없다.

    ITA° = arctan((L* - 50) / b*) × 180/π
    홍반 지수 = a* (적록 축. 값이 클수록 붉다)

── 변환 경로 ───────────────────────────────────────────────────────
    채널값 → 반사율 → XYZ 삼자극치 → L*a*b*

1) 반사율. 백색 표준판으로 나눈다. 이 단계가 없으면 LED 밝기와 채널별
   감도가 그대로 색에 섞인다. 화장품 쪽과 같은 이유지만, 여기서는
   백색 기준이 선택이 아니라 필수다. 절대 색을 말하려면 기준이 있어야 한다.

2) XYZ. 반사율 스펙트럼에 D65 광원과 CIE 1931 2° 등색함수를 곱해 적분한다.
   D65를 쓰는 이유는 피부색 문헌이 대부분 D65 기준으로 Lab을 보고하기
   때문이다. 실제 조명은 노드의 백색 LED지만, 1)에서 백색 표준판으로
   나눈 시점에 LED의 스펙트럼은 상쇄된다.

3) Lab. 표준 변환식.

── 이 변환의 한계 ──────────────────────────────────────────────────
AS7341은 415~680nm를 여덟 점으로만 샘플링한다. 진짜 분광광도계는 같은
구간을 5nm 간격 쉰 점 이상으로 잰다. 여덟 점 적분은 그 근사이고,
특히 380~415nm와 680~780nm는 아예 데이터가 없다.

그래서 여기서 나오는 Lab을 분광광도계 값과 같다고 말할 수 없다.
우리가 쓰는 방식은 같은 장비로 같은 부위를 반복해서 재고 그 변화를 보는
것이라, 절대값의 정확도보다 반복 측정의 일관성이 중요하다. 절대값으로
판정하지 않는다는 원칙(db/iot/skin_reader)이 여기서 나온다.

백색점도 같은 여덟 점으로 계산한다. 표준 D65 백색점(95.047, 100, 108.883)을
쓰면 잘려나간 구간만큼 어긋나, 완전 백색을 재도 L*이 100이 되지 않는다.
같은 방식으로 계산한 백색점을 쓰면 완전 반사체가 정확히 L*=100, a*=b*=0이
된다.
"""
from __future__ import annotations

import logging
import math

from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# AS7341 여덟 채널의 중심 파장(nm).
CHANNELS: Tuple[str, ...] = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8")
WAVELENGTHS: Tuple[int, ...] = (415, 445, 480, 515, 555, 590, 630, 680)

# CIE 1931 2° 표준 관측자 등색함수. 위 여덟 파장에서의 값.
CIE_X = (0.07763, 0.34806, 0.09564, 0.02910, 0.51205, 1.02630, 0.64240, 0.04677)
CIE_Y = (0.00218, 0.02980, 0.13902, 0.60820, 1.00000, 0.75700, 0.26500, 0.01700)
CIE_Z = (0.37130, 1.78260, 0.81295, 0.11170, 0.00575, 0.00110, 0.00005, 0.00000)

# 표준광 D65의 상대 분광분포. 560nm에서 100으로 정규화된 표준값.
D65 = (92.46, 110.94, 115.92, 106.30, 102.02, 88.69, 83.29, 78.28)

# 각 채널이 대표하는 파장 폭(nm).
#
# 채널 간격이 고르지 않다(415→445는 30nm, 630→680은 50nm). 같은 무게로
# 더하면 간격이 넓은 장파장 쪽이 실제보다 적게 반영되어 색이 푸른 쪽으로
# 치우친다. 이웃까지 거리의 절반씩을 그 채널의 몫으로 잡는다(사다리꼴 적분).
BANDWIDTH = (30.0, 32.5, 35.0, 37.5, 37.5, 37.5, 45.0, 45.0)

# 반사율 상한. 1을 넘는 것은 백색 표준판보다 밝게 잡혔다는 뜻으로, 대개
# 정반사(번들거림)나 밀착 실패다. 그대로 두면 L*이 100을 크게 넘는 값이
# 나오므로 자른다. 자른 사실은 호출부가 알 수 있게 saturated로 함께 돌려준다.
MAX_REFLECTANCE = 1.5


def _weights() -> List[Tuple[float, float, float, float]]:
    """채널별 (D65 × 등색함수 × 파장폭) 가중치."""
    return [
        (D65[i] * CIE_X[i] * BANDWIDTH[i],
         D65[i] * CIE_Y[i] * BANDWIDTH[i],
         D65[i] * CIE_Z[i] * BANDWIDTH[i],
         0.0)
        for i in range(len(CHANNELS))
    ]


_W = _weights()

# 완전 반사체(반사율 1)의 삼자극치. 이것이 이 장비의 백색점이다.
WHITE_X = sum(w[0] for w in _W)
WHITE_Y = sum(w[1] for w in _W)
WHITE_Z = sum(w[2] for w in _W)


def reflectance(
    channels: Dict[str, Any],
    white_ref: Optional[Dict[str, Any]],
) -> Optional[List[float]]:
    """
    여덟 채널의 반사율. 하나라도 빠지면 None.

    화장품 쪽(optical.reflectance)은 백색 기준이 없으면 원값을 그대로
    썼지만, 여기서는 그럴 수 없다. 반사율이 아닌 값을 색으로 옮기면
    조명 밝기가 그대로 피부색이 된다.
    """
    if not white_ref:
        return None

    out: List[float] = []
    for k in CHANNELS:
        try:
            v = float(channels[k])
            w = float(white_ref[k])
        except (KeyError, TypeError, ValueError):
            return None
        if w <= 0:
            return None
        out.append(max(0.0, min(v / w, MAX_REFLECTANCE)))
    return out


def to_xyz(
    channels: Dict[str, Any],
    white_ref: Optional[Dict[str, Any]],
) -> Optional[Tuple[float, float, float]]:
    """반사율 스펙트럼을 D65 기준 XYZ로. 백색점은 Y=100으로 맞춘다."""
    r = reflectance(channels, white_ref)
    if r is None:
        return None

    x = sum(r[i] * _W[i][0] for i in range(len(r)))
    y = sum(r[i] * _W[i][1] for i in range(len(r)))
    z = sum(r[i] * _W[i][2] for i in range(len(r)))

    scale = 100.0 / WHITE_Y
    return (x * scale, y * scale, z * scale)


def _f(t: float) -> float:
    """Lab 변환의 비선형 압축. 어두운 쪽에서 기울기가 발산하지 않게 잘라 쓴다."""
    return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (841.0 / 108.0) * t + 4.0 / 29.0


def to_lab(
    channels: Dict[str, Any],
    white_ref: Optional[Dict[str, Any]],
) -> Optional[Tuple[float, float, float]]:
    """
    L*a*b*. 변환할 수 없으면 None.

    백색점은 표준 D65가 아니라 같은 여덟 점으로 계산한 이 장비의 백색점을
    쓴다(모듈 설명 참고). 완전 반사체가 정확히 L*=100, a*=b*=0이 된다.
    """
    xyz = to_xyz(channels, white_ref)
    if xyz is None:
        return None

    x, y, z = xyz
    scale = 100.0 / WHITE_Y
    fx = _f(x / (WHITE_X * scale))
    fy = _f(y / 100.0)
    fz = _f(z / (WHITE_Z * scale))

    return (
        round(116.0 * fy - 16.0, 2),
        round(500.0 * (fx - fy), 2),
        round(200.0 * (fy - fz), 2),
    )
